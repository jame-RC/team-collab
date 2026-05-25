"""Tests for teamcollab.conflict.

Two clones racing on the same shared file (glossary.json) must both land
successfully via the pull-modify-push retry layer. This is the canonical
"hot file" scenario for the project.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from git import Repo

from teamcollab.conflict import RetryResult, with_pull_modify_push_retry
from teamcollab.git_ops import GitRepo


# ---------------------------------------------------------------------------
# Fixtures: a bare remote + two working clones, all on disk in tmp_path
# ---------------------------------------------------------------------------


@pytest.fixture
def shared_remote(tmp_path: Path) -> Path:
    """A bare remote with an initial empty glossary.json committed."""
    seed = tmp_path / "seed"
    seed_repo = GitRepo.init(seed, initial_branch="main")
    seed_repo._repo.git.config("user.email", "seed@e.com")
    seed_repo._repo.git.config("user.name", "seed")
    (seed / "glossary.json").write_text("{}\n", encoding="utf-8")
    seed_repo.add([seed / "glossary.json"])
    seed_repo.commit("seed glossary")

    bare = tmp_path / "remote.git"
    Repo.init(bare, bare=True, initial_branch="main")
    seed_repo._repo.create_remote("origin", str(bare))
    seed_repo._repo.git.push("-u", "origin", "main")
    return bare


def _make_clone(name: str, tmp_path: Path, remote: Path) -> GitRepo:
    clone_path = tmp_path / name
    clone = GitRepo.clone(str(remote), clone_path)
    clone._repo.git.config("user.email", f"{name}@e.com")
    clone._repo.git.config("user.name", name)
    return clone


def _set_term(repo_path: Path, key: str, value: str):
    """A modify_fn closure factory: edit glossary.json by setting one key."""
    def _modify(work: Path):
        f = work / "glossary.json"
        data = json.loads(f.read_text(encoding="utf-8"))
        data[key] = value
        f.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return [f]
    return _modify


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_retry_no_contention_pushes_first_try(tmp_path: Path, shared_remote: Path):
    alice = _make_clone("alice", tmp_path, shared_remote)
    result = with_pull_modify_push_retry(
        alice,
        _set_term(alice.path, "mlops", "Machine Learning Operations"),
        commit_message="add mlops",
    )
    assert isinstance(result, RetryResult)
    assert result.attempts == 1
    assert result.pushed is True
    assert result.sha is not None


def test_retry_returns_none_sha_when_modify_is_a_noop(
    tmp_path: Path, shared_remote: Path
):
    alice = _make_clone("alice", tmp_path, shared_remote)

    def _no_change(_work: Path):
        return None  # touched nothing

    result = with_pull_modify_push_retry(
        alice, _no_change, commit_message="noop"
    )
    assert result.sha is None
    assert result.pushed is True


# ---------------------------------------------------------------------------
# The core scenario: two members racing on glossary.json
# ---------------------------------------------------------------------------


def test_two_clones_racing_both_writes_survive(tmp_path: Path, shared_remote: Path):
    alice = _make_clone("alice", tmp_path, shared_remote)
    bob = _make_clone("bob", tmp_path, shared_remote)

    # Alice writes first and pushes (clean, no contention).
    r1 = with_pull_modify_push_retry(
        alice,
        _set_term(alice.path, "mlops", "Machine Learning Operations"),
        commit_message="alice: mlops",
    )
    assert r1.pushed and r1.attempts == 1

    # Bob is unaware of alice's write — his local clone is now stale.
    # He attempts to add a different key. First push will be rejected
    # (non-fast-forward); the retry layer must pull --rebase and re-apply.
    r2 = with_pull_modify_push_retry(
        bob,
        _set_term(bob.path, "rag", "Retrieval Augmented Generation"),
        commit_message="bob: rag",
    )
    assert r2.pushed is True
    assert r2.attempts >= 1  # may be 1 if rebase happened during pull, or 2 if push rejected

    # Verify both keys present in remote: clone fresh and inspect.
    final = _make_clone("verifier", tmp_path, shared_remote)
    glossary = json.loads((final.path / "glossary.json").read_text(encoding="utf-8"))
    assert glossary.get("mlops") == "Machine Learning Operations"
    assert glossary.get("rag") == "Retrieval Augmented Generation"


def test_modify_fn_sees_freshly_pulled_state_on_retry(
    tmp_path: Path, shared_remote: Path
):
    """On a rebase retry, modify_fn must run against the *new* tree, not
    the stale one captured at the first attempt. We assert this by having
    modify_fn read the file each call and merge into whatever it finds.
    """
    alice = _make_clone("alice", tmp_path, shared_remote)
    bob = _make_clone("bob", tmp_path, shared_remote)

    # Alice publishes a commit Bob doesn't have.
    with_pull_modify_push_retry(
        alice,
        _set_term(alice.path, "alpha", "first"),
        commit_message="alice: alpha",
    )

    # Bob's modify_fn reads-then-writes; on retry it should see "alpha"
    # already present and add "beta" alongside it (not clobber it).
    call_count = {"n": 0}

    def _bob_adds_beta(work: Path):
        call_count["n"] += 1
        f = work / "glossary.json"
        data = json.loads(f.read_text(encoding="utf-8"))
        data["beta"] = "second"
        f.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return [f]

    result = with_pull_modify_push_retry(
        bob, _bob_adds_beta, commit_message="bob: beta"
    )
    assert result.pushed

    # Cross-check: both keys are present in the final remote state.
    verifier = _make_clone("v2", tmp_path, shared_remote)
    glossary = json.loads(
        (verifier.path / "glossary.json").read_text(encoding="utf-8")
    )
    assert glossary == {"alpha": "first", "beta": "second"}
