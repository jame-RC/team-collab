"""Tests for teamcollab.git_ops using a temp local repo + a bare 'remote'."""
from __future__ import annotations

from pathlib import Path

import pytest
from git import Repo

from teamcollab.contracts import EventEnvelope, EventType
from teamcollab.git_ops import (
    AuthError,
    ConflictError,
    GitRepo,
    OfflineError,
    RepoNotFoundError,
    _classify,
)
from git import GitCommandError


# ---------------------------------------------------------------------------
# Fixtures: a bare "remote" + a working clone, all on disk in tmp_path
# ---------------------------------------------------------------------------


@pytest.fixture
def bare_remote(tmp_path: Path) -> Path:
    bare = tmp_path / "remote.git"
    Repo.init(bare, bare=True, initial_branch="main")
    return bare


@pytest.fixture
def working_repo(tmp_path: Path, bare_remote: Path) -> GitRepo:
    work = tmp_path / "work"
    repo = GitRepo.init(work, initial_branch="main")
    # Need an initial commit before we can add a remote and push.
    (work / "README.md").write_text("hello\n", encoding="utf-8")
    repo.add([work / "README.md"])
    repo.commit("init")
    repo._repo.create_remote("origin", str(bare_remote))
    repo._repo.git.push("-u", "origin", "main")
    # Configure user identity for subsequent commits
    repo._repo.git.config("user.email", "test@example.com")
    repo._repo.git.config("user.name", "test")
    return repo


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_repo_not_found(tmp_path: Path):
    with pytest.raises(RepoNotFoundError):
        GitRepo(tmp_path / "does-not-exist")


def test_init_creates_repo(tmp_path: Path):
    repo = GitRepo.init(tmp_path / "fresh")
    assert repo.path.exists()
    assert (repo.path / ".git").exists()


# ---------------------------------------------------------------------------
# Commit + log + EventEnvelope round-trip via git
# ---------------------------------------------------------------------------


def test_commit_and_log_roundtrip(working_repo: GitRepo):
    f = working_repo.path / "tasks" / "task-001.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("{}\n", encoding="utf-8")
    working_repo.add([f])

    envelope = EventEnvelope(
        type=EventType.TASKS_DEFINED, actor="alice", task_id="task-001"
    )
    sha = working_repo.commit(envelope.dump("defined first task"))
    assert sha is not None

    log = working_repo.log(max_count=10)
    assert log[0].sha == sha
    parsed = EventEnvelope.parse(log[0].message)
    assert parsed is not None
    assert parsed.type == EventType.TASKS_DEFINED
    assert parsed.actor == "alice"


def test_commit_returns_none_when_nothing_staged(working_repo: GitRepo):
    assert working_repo.commit("noop") is None


def test_log_since_sha(working_repo: GitRepo):
    base = working_repo.head_sha()
    for i in range(3):
        f = working_repo.path / f"f{i}.txt"
        f.write_text(str(i), encoding="utf-8")
        working_repo.add([f])
        working_repo.commit(f"c{i}")
    log = working_repo.log(since_sha=base)
    assert len(log) == 3


# ---------------------------------------------------------------------------
# Push / pull happy path
# ---------------------------------------------------------------------------


def test_push_pull_happy_path(tmp_path: Path, working_repo: GitRepo, bare_remote: Path):
    # Make a change and push.
    f = working_repo.path / "a.txt"
    f.write_text("a", encoding="utf-8")
    working_repo.add([f])
    working_repo.commit("add a")
    working_repo.push(branch="main")

    # Clone fresh from bare and verify the file is there.
    clone_path = tmp_path / "clone"
    clone = GitRepo.clone(str(bare_remote), clone_path)
    assert (clone.path / "a.txt").exists()


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------


def _fake(stderr: str) -> GitCommandError:
    return GitCommandError(["git", "x"], 1, stderr.encode(), b"")


def test_classify_offline():
    assert isinstance(_classify(_fake("Could not resolve host: github.com")), OfflineError)


def test_classify_auth():
    assert isinstance(_classify(_fake("fatal: Authentication failed")), AuthError)


def test_classify_conflict():
    assert isinstance(
        _classify(_fake("! [rejected]        main -> main (non-fast-forward)")),
        ConflictError,
    )


def test_clone_offline_classified(tmp_path: Path):
    """Clone from an unreachable URL: should raise OfflineError or AuthError, not bare GitCommandError."""
    fake_url = "https://no-such-host-xyz-teamcollab.invalid/repo.git"
    with pytest.raises((OfflineError, AuthError)):
        GitRepo.clone(fake_url, tmp_path / "clone")
