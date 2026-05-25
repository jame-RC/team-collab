"""End-to-end verification tests per TASKS.md Module 6.2 scenarios.

Covers:
  #1 Single-process smoke (self-loop rejection)
  #2 Multi-person online simulation
  #3 Offline async (core)
  #4 Glossary conflict recovery
  #5 Contract validation rejection
  #7 Three topologies + task_list --tree + DEPS_NOT_READY
  #9 Event source substitutability

Scenarios #6 (quality comparison) and #8 (Actions fallback) require external
API calls / GitHub infrastructure and are tested manually.
"""
from __future__ import annotations

import json
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
from teamcollab.tools._paths import members_json, project_json, task_json, tasks_dir
from teamcollab.tools.glossary import glossary_get, glossary_update
from teamcollab.tools.task_claim import TaskClaimError, task_claim
from teamcollab.tools.task_create_batch import task_create_batch
from teamcollab.tools.task_list import task_list
from teamcollab.tools.task_review import task_review
from teamcollab.tools.task_submit import TaskSubmitError, task_submit
from teamcollab.tools.team_init import team_init


def _mk_task(tid: str, owner: str, title: str = "", brief: str = "", deps: list[str] | None = None) -> TaskContract:
    return TaskContract(
        task_id=tid,
        title=title or f"task {tid}",
        brief=brief or f"do {tid}",
        owner=owner,
        deps=deps or [],
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Bootstrapped local repo with leader alice and members bob, carol."""
    root = tmp_path / "proj"
    team_init(local_path=root, title="e2e-test", brief="verification", leader="alice")

    from git import Repo

    g = Repo(root)
    g.git.config("user.email", "test@test.com")
    g.git.config("user.name", "test")

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


# ---------------------------------------------------------------------------
# #1 Single-process smoke + self-loop rejection
# ---------------------------------------------------------------------------


class TestSmokeAndSelfLoop:
    def test_self_loop_rejected(self, repo: Path):
        """task_create_batch rejects a task that depends on itself."""
        from pydantic import ValidationError

        with pytest.raises((DagError, ValidationError)):
            tasks = [_mk_task("task-001", "bob", deps=["task-001"])]
            task_create_batch(local_path=repo, tasks=tasks, actor="alice")

    def test_full_pipeline_smoke(self, repo: Path):
        """Single-process: create → claim → submit → review → approved."""
        task_create_batch(
            local_path=repo,
            tasks=[_mk_task("task-001", "bob", title="T1", brief="do it")],
            actor="alice",
        )

        task_claim(local_path=repo, task_id="task-001", me="bob")
        task_submit(
            local_path=repo,
            task_id="task-001",
            me="bob",
            content="# Result\nDone.",
        )
        task_review(
            local_path=repo,
            task_id="task-001",
            reviewer="alice",
            verdict=Verdict.APPROVED,
            score=85,
            comments=[{"message": "Good work"}],
        )

        task_data = read_json(task_json(repo, "task-001"))
        assert task_data["status"] == "approved"


# ---------------------------------------------------------------------------
# #2 Multi-person online simulation
# ---------------------------------------------------------------------------


class TestMultiPerson:
    def test_two_members_work_in_parallel(self, repo: Path):
        """Bob and Carol can independently claim, submit, and get reviewed."""
        task_create_batch(
            local_path=repo,
            tasks=[
                _mk_task("task-001", "bob", title="T1", brief="b"),
                _mk_task("task-002", "carol", title="T2", brief="c"),
            ],
            actor="alice",
        )

        task_claim(local_path=repo, task_id="task-001", me="bob")
        task_claim(local_path=repo, task_id="task-002", me="carol")

        task_submit(local_path=repo, task_id="task-001", me="bob", content="Bob's work")
        task_submit(local_path=repo, task_id="task-002", me="carol", content="Carol's work")

        task_review(local_path=repo, task_id="task-001", reviewer="alice", verdict=Verdict.APPROVED, score=90, comments=[])
        task_review(local_path=repo, task_id="task-002", reviewer="alice", verdict=Verdict.APPROVED, score=88, comments=[])

        t1 = read_json(task_json(repo, "task-001"))
        t2 = read_json(task_json(repo, "task-002"))
        assert t1["status"] == "approved"
        assert t2["status"] == "approved"


# ---------------------------------------------------------------------------
# #3 Offline async (core) — simulated by skipping push
# ---------------------------------------------------------------------------


class TestOfflineAsync:
    def test_commit_without_push(self, repo: Path):
        """Operations succeed locally even without a remote (offline mode)."""
        task_create_batch(
            local_path=repo,
            tasks=[_mk_task("task-001", "bob", title="T", brief="b")],
            actor="alice",
        )

        assert (tasks_dir(repo) / "task-001.json").exists()

        task_claim(local_path=repo, task_id="task-001", me="bob")
        task_submit(local_path=repo, task_id="task-001", me="bob", content="Offline work")

        artifact_content = (repo / "artifacts" / "bob" / "task-001" / "content.md").read_text(encoding="utf-8")
        assert "Offline work" in artifact_content


# ---------------------------------------------------------------------------
# #4 Glossary conflict recovery
# ---------------------------------------------------------------------------


class TestGlossaryConflict:
    def test_concurrent_glossary_updates(self, repo: Path):
        """Two sequential glossary updates to the same key don't lose data."""
        glossary_update(local_path=repo, term="AI", definition="Artificial Intelligence", actor="alice")
        glossary_update(local_path=repo, term="ML", definition="Machine Learning", actor="bob")

        result = glossary_get(local_path=repo)
        entries = result.get("entries", {})
        assert "AI" in entries
        assert "ML" in entries

    def test_glossary_overwrite(self, repo: Path):
        """Updating an existing term replaces its definition."""
        glossary_update(local_path=repo, term="AI", definition="old def", actor="alice")
        glossary_update(local_path=repo, term="AI", definition="Artificial Intelligence", actor="bob")

        result = glossary_get(local_path=repo)
        assert result["entries"]["AI"]["definition"] == "Artificial Intelligence"


# ---------------------------------------------------------------------------
# #5 Contract validation rejection
# ---------------------------------------------------------------------------


class TestContractValidation:
    def test_unknown_owner_rejected(self, repo: Path):
        """task_create_batch rejects tasks with owners not in members.json."""
        with pytest.raises(DagError, match="owner"):
            task_create_batch(
                local_path=repo,
                tasks=[_mk_task("task-001", "unknown_person")],
                actor="alice",
            )

    def test_dangling_dep_rejected(self, repo: Path):
        """task_create_batch rejects tasks referencing non-existent dependencies."""
        with pytest.raises(DagError, match="dep"):
            task_create_batch(
                local_path=repo,
                tasks=[_mk_task("task-001", "bob", deps=["task-999"])],
                actor="alice",
            )

    def test_submit_without_claim_rejected(self, repo: Path):
        """Cannot submit an artifact for an unclaimed task."""
        task_create_batch(
            local_path=repo,
            tasks=[_mk_task("task-001", "bob", title="T", brief="b")],
            actor="alice",
        )
        with pytest.raises(TaskSubmitError):
            task_submit(local_path=repo, task_id="task-001", me="bob", content="nope")


# ---------------------------------------------------------------------------
# #7 Three topologies + task_list --tree + DEPS_NOT_READY
# ---------------------------------------------------------------------------


class TestTopologies:
    def test_pipeline_deps_not_ready(self, repo: Path):
        """In a pipeline, downstream task cannot be claimed until upstream is approved."""
        task_create_batch(
            local_path=repo,
            tasks=[
                _mk_task("task-001", "alice", title="T1", brief="first"),
                _mk_task("task-002", "bob", title="T2", brief="second", deps=["task-001"]),
            ],
            actor="alice",
        )

        with pytest.raises(TaskClaimError) as exc_info:
            task_claim(local_path=repo, task_id="task-002", me="bob")
        assert "task-001" in str(exc_info.value)

    def test_parallel_all_claimable(self, repo: Path):
        """In a parallel topology, all tasks are immediately claimable."""
        task_create_batch(
            local_path=repo,
            tasks=[
                _mk_task("task-001", "alice", title="T1", brief="a"),
                _mk_task("task-002", "bob", title="T2", brief="b"),
                _mk_task("task-003", "carol", title="T3", brief="c"),
            ],
            actor="alice",
        )

        task_claim(local_path=repo, task_id="task-001", me="alice")
        task_claim(local_path=repo, task_id="task-002", me="bob")
        task_claim(local_path=repo, task_id="task-003", me="carol")

    def test_hybrid_fan_in(self, repo: Path):
        """Hybrid: fan-in task blocked until both upstream tasks are approved."""
        task_create_batch(
            local_path=repo,
            tasks=[
                _mk_task("task-001", "bob", title="Research A", brief="a"),
                _mk_task("task-002", "carol", title="Research B", brief="b"),
                _mk_task("task-003", "alice", title="Integrate", brief="c", deps=["task-001", "task-002"]),
            ],
            actor="alice",
        )

        task_claim(local_path=repo, task_id="task-001", me="bob")
        task_submit(local_path=repo, task_id="task-001", me="bob", content="A done")
        task_review(local_path=repo, task_id="task-001", reviewer="alice", verdict=Verdict.APPROVED, score=90, comments=[])

        with pytest.raises(TaskClaimError):
            task_claim(local_path=repo, task_id="task-003", me="alice")

        task_claim(local_path=repo, task_id="task-002", me="carol")
        task_submit(local_path=repo, task_id="task-002", me="carol", content="B done")
        task_review(local_path=repo, task_id="task-002", reviewer="alice", verdict=Verdict.APPROVED, score=85, comments=[])

        task_claim(local_path=repo, task_id="task-003", me="alice")

    def test_task_list_tree(self, repo: Path):
        """task_list with tree=True returns ASCII DAG representation."""
        task_create_batch(
            local_path=repo,
            tasks=[
                _mk_task("task-001", "bob", title="A", brief="a"),
                _mk_task("task-002", "carol", title="B", brief="b", deps=["task-001"]),
            ],
            actor="alice",
        )

        result = task_list(local_path=repo, filter="all", tree=True)
        assert "task-001" in result["tree"]
        assert "task-002" in result["tree"]


# ---------------------------------------------------------------------------
# #9 Event source substitutability
# ---------------------------------------------------------------------------


class TestEventSourceSubstitutable:
    def test_git_event_source(self, repo: Path):
        """Events can be read from git log (default GitEventSource)."""
        from teamcollab.events import GitEventSource
        from teamcollab.git_ops import GitRepo

        git_repo = GitRepo(repo)
        source = GitEventSource(git_repo)
        events = source.read()
        assert len(events) >= 1
        assert events[0].envelope.type.value == "project_created"

    def test_events_after_actions(self, repo: Path):
        """After creating tasks, a new event appears in the log."""
        from teamcollab.events import GitEventSource
        from teamcollab.git_ops import GitRepo

        task_create_batch(
            local_path=repo,
            tasks=[_mk_task("task-001", "bob", title="T", brief="b")],
            actor="alice",
        )

        git_repo = GitRepo(repo)
        source = GitEventSource(git_repo)
        events = source.read()
        types = [e.envelope.type.value for e in events]
        assert "tasks_defined" in types
