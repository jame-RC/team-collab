"""Minimum coverage tests for the task / artifact / review / list tools.

One success path + one failure path per tool, per M1.6 acceptance.

Fixture strategy: every test gets a freshly bootstrapped local repo (via
``team_init``) plus two extra members appended to ``members.json`` so we
can exercise multi-member flows (claim, submit, review) without needing a
real remote. ``remote_url=None`` means no push is attempted, which keeps
these tests hermetic.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from teamcollab.contracts import (
    MemberInfo,
    ProjectMeta,
    Role,
    TaskContract,
    TaskStatus,
    Verdict,
)
from teamcollab.tools._dag import DagError
from teamcollab.tools._io import read_json, read_model, write_json, write_model
from teamcollab.tools._paths import (
    members_json,
    project_json,
    review_json,
    task_json,
)
from teamcollab.tools.read_artifact import ArtifactNotFoundError, read_artifact
from teamcollab.tools.task_add import task_add
from teamcollab.tools.task_claim import TaskClaimError, task_claim
from teamcollab.tools.task_create_batch import task_create_batch
from teamcollab.tools.task_list import task_list
from teamcollab.tools.task_review import task_review
from teamcollab.tools.task_submit import TaskSubmitError, task_submit
from teamcollab.tools.team_init import team_init


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo_path(tmp_path: Path) -> Path:
    """Bootstrapped local repo with leader 'alice' and members bob, carol."""
    root = tmp_path / "proj"
    team_init(
        local_path=root,
        title="demo",
        brief="a demo project",
        leader="alice",
    )

    # Configure git identity so subsequent commits don't blow up on default config.
    from git import Repo
    g = Repo(root)
    g.git.config("user.email", "test@example.com")
    g.git.config("user.name", "test")

    # Append bob and carol to members.json + project.json so they're known owners.
    extra = [
        MemberInfo(name="bob", role=Role.MEMBER),
        MemberInfo(name="carol", role=Role.MEMBER),
    ]
    members_raw = read_json(members_json(root))
    members_raw.extend(m.model_dump(mode="json") for m in extra)
    write_json(members_json(root), members_raw)

    project = read_model(project_json(root), ProjectMeta)
    project = project.model_copy(update={"members": project.members + extra})
    write_model(project_json(root), project)

    return root


def _mk_task(tid: str, owner: str, deps: list[str] | None = None) -> TaskContract:
    return TaskContract(
        task_id=tid,
        title=f"task {tid}",
        brief=f"do {tid}",
        owner=owner,
        deps=deps or [],
    )


# ---------------------------------------------------------------------------
# task_create_batch
# ---------------------------------------------------------------------------


def test_create_batch_success(repo_path: Path):
    tasks = [_mk_task("task-001", "bob"), _mk_task("task-002", "carol", deps=["task-001"])]
    out = task_create_batch(local_path=repo_path, tasks=tasks, actor="alice")
    assert len(out["task_ids"]) == 2
    assert task_json(repo_path, "task-001").exists()
    assert task_json(repo_path, "task-002").exists()


def test_create_batch_rejects_cycle(repo_path: Path):
    a = _mk_task("task-001", "bob", deps=["task-002"])
    b = _mk_task("task-002", "carol", deps=["task-001"])
    with pytest.raises(DagError):
        task_create_batch(local_path=repo_path, tasks=[a, b], actor="alice")


# ---------------------------------------------------------------------------
# task_add
# ---------------------------------------------------------------------------


def test_task_add_success(repo_path: Path):
    out = task_add(local_path=repo_path, task=_mk_task("task-010", "bob"), actor="alice")
    assert out["task_id"] == "task-010"
    assert task_json(repo_path, "task-010").exists()


def test_task_add_unknown_owner(repo_path: Path):
    bogus = _mk_task("task-099", "ghost")
    with pytest.raises(DagError):
        task_add(local_path=repo_path, task=bogus, actor="alice")


# ---------------------------------------------------------------------------
# task_list
# ---------------------------------------------------------------------------


def test_task_list_filters_and_tree(repo_path: Path):
    task_create_batch(
        local_path=repo_path,
        tasks=[
            _mk_task("task-001", "bob"),
            _mk_task("task-002", "carol", deps=["task-001"]),
        ],
        actor="alice",
    )
    out = task_list(local_path=repo_path, filter="available", tree=True)
    avail_ids = {t["task_id"] for t in out["tasks"]}
    assert avail_ids == {"task-001"}  # task-002 is blocked by task-001
    assert "tree" in out and "task-001" in out["tree"]

    blocked = task_list(local_path=repo_path, filter="blocked")
    blocked_ids = {t["task_id"] for t in blocked["tasks"]}
    assert blocked_ids == {"task-002"}
    waiting = next(t["waiting_for"] for t in blocked["tasks"] if t["task_id"] == "task-002")
    assert waiting == ["task-001"]


def test_task_list_mine_requires_me(repo_path: Path):
    task_create_batch(
        local_path=repo_path,
        tasks=[_mk_task("task-001", "bob")],
        actor="alice",
    )
    out = task_list(local_path=repo_path, filter="mine", me="bob")
    assert {t["task_id"] for t in out["tasks"]} == {"task-001"}
    out_other = task_list(local_path=repo_path, filter="mine", me="carol")
    assert out_other["count"] == 0


# ---------------------------------------------------------------------------
# task_claim
# ---------------------------------------------------------------------------


def test_claim_success(repo_path: Path):
    task_create_batch(
        local_path=repo_path,
        tasks=[_mk_task("task-001", "bob")],
        actor="alice",
    )
    task_claim(local_path=repo_path, task_id="task-001", me="bob")
    t = read_model(task_json(repo_path, "task-001"), TaskContract)
    assert t.status == TaskStatus.CLAIMED
    assert t.owner == "bob"
    assert t.claimed_at is not None


def test_claim_blocked_by_deps(repo_path: Path):
    task_create_batch(
        local_path=repo_path,
        tasks=[
            _mk_task("task-001", "bob"),
            _mk_task("task-002", "carol", deps=["task-001"]),
        ],
        actor="alice",
    )
    with pytest.raises(TaskClaimError) as ei:
        task_claim(local_path=repo_path, task_id="task-002", me="carol")
    assert ei.value.code == "DEPS_NOT_READY"
    assert ei.value.payload["waiting_for"] == ["task-001"]


# ---------------------------------------------------------------------------
# task_submit
# ---------------------------------------------------------------------------


def test_submit_success(repo_path: Path):
    task_create_batch(
        local_path=repo_path,
        tasks=[_mk_task("task-001", "bob")],
        actor="alice",
    )
    task_claim(local_path=repo_path, task_id="task-001", me="bob")
    out = task_submit(
        local_path=repo_path,
        task_id="task-001",
        me="bob",
        content="# my work\nbody",
    )
    assert out["artifact_path"].endswith("content.md")
    art_path = repo_path / out["artifact_path"]
    assert art_path.read_text(encoding="utf-8").startswith("# my work")
    t = read_model(task_json(repo_path, "task-001"), TaskContract)
    assert t.status == TaskStatus.SUBMITTED


def test_submit_not_owner(repo_path: Path):
    task_create_batch(
        local_path=repo_path,
        tasks=[_mk_task("task-001", "bob")],
        actor="alice",
    )
    task_claim(local_path=repo_path, task_id="task-001", me="bob")
    with pytest.raises(TaskSubmitError) as ei:
        task_submit(
            local_path=repo_path,
            task_id="task-001",
            me="carol",
            content="not mine",
        )
    assert ei.value.code == "NOT_OWNER"


# ---------------------------------------------------------------------------
# task_review
# ---------------------------------------------------------------------------


def test_review_approved_unblocks_downstream(repo_path: Path):
    task_create_batch(
        local_path=repo_path,
        tasks=[
            _mk_task("task-001", "bob"),
            _mk_task("task-002", "carol", deps=["task-001"]),
        ],
        actor="alice",
    )
    task_claim(local_path=repo_path, task_id="task-001", me="bob")
    task_submit(
        local_path=repo_path,
        task_id="task-001",
        me="bob",
        content="done",
    )
    out = task_review(
        local_path=repo_path,
        task_id="task-001",
        reviewer="alice",
        verdict=Verdict.APPROVED,
        score=90,
        comments=[],
    )
    assert out["new_status"] == TaskStatus.APPROVED.value
    assert review_json(repo_path, "task-001").exists()

    # Downstream task-002 should now appear in `available`.
    avail = task_list(local_path=repo_path, filter="available")
    assert "task-002" in {t["task_id"] for t in avail["tasks"]}


def test_review_needs_revision_lets_owner_resubmit(repo_path: Path):
    task_create_batch(
        local_path=repo_path,
        tasks=[_mk_task("task-001", "bob")],
        actor="alice",
    )
    task_claim(local_path=repo_path, task_id="task-001", me="bob")
    task_submit(local_path=repo_path, task_id="task-001", me="bob", content="v1")
    task_review(
        local_path=repo_path,
        task_id="task-001",
        reviewer="alice",
        verdict=Verdict.NEEDS_REVISION,
        score=50,
        comments=[],
    )
    t = read_model(task_json(repo_path, "task-001"), TaskContract)
    assert t.status == TaskStatus.NEEDS_REVISION
    # Owner can resubmit despite status != claimed
    task_submit(local_path=repo_path, task_id="task-001", me="bob", content="v2")
    t = read_model(task_json(repo_path, "task-001"), TaskContract)
    assert t.status == TaskStatus.SUBMITTED


# ---------------------------------------------------------------------------
# read_artifact
# ---------------------------------------------------------------------------


def test_read_artifact_success(repo_path: Path):
    task_create_batch(
        local_path=repo_path,
        tasks=[_mk_task("task-001", "bob")],
        actor="alice",
    )
    task_claim(local_path=repo_path, task_id="task-001", me="bob")
    task_submit(local_path=repo_path, task_id="task-001", me="bob", content="hello")
    out = read_artifact(local_path=repo_path, member="bob", task_id="task-001")
    assert out["content"] == "hello"
    assert out["artifact"]["actor"] == "bob"


def test_read_artifact_missing(repo_path: Path):
    with pytest.raises(ArtifactNotFoundError) as ei:
        read_artifact(local_path=repo_path, member="bob", task_id="task-999")
    assert ei.value.code == "ARTIFACT_NOT_FOUND"
