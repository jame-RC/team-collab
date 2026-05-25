"""Tests for teamcollab.events.

Covers two things the architecture cares about:

1. Read path correctness over git source (filter by type / since_id / limit).
2. Source replaceability: a mock :class:`EventSource` (no git) must work
   through ``read_events`` unchanged. This is the "C 节" guarantee from PLAN —
   if we ever swap git for Webhook/NATS, upstream code is unaffected.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from teamcollab.contracts import EventEnvelope, EventType
from teamcollab.events import EventRecord, EventSource, GitEventSource, read_events
from teamcollab.git_ops import GitRepo


@pytest.fixture
def repo_with_events(tmp_path: Path) -> GitRepo:
    repo = GitRepo.init(tmp_path / "r", initial_branch="main")
    repo._repo.git.config("user.email", "t@e.com")
    repo._repo.git.config("user.name", "t")

    # First commit: a non-envelope (legacy) commit.
    (repo.path / "README.md").write_text("hi", encoding="utf-8")
    repo.add([repo.path / "README.md"])
    repo.commit("plain old commit, not an envelope")

    # Then three envelope commits.
    for i, etype in enumerate(
        [EventType.PROJECT_CREATED, EventType.TASKS_DEFINED, EventType.TASK_CLAIMED]
    ):
        f = repo.path / f"f{i}.txt"
        f.write_text(str(i), encoding="utf-8")
        repo.add([f])
        env = EventEnvelope(type=etype, actor="alice", task_id=f"task-{i:03d}")
        repo.commit(env.dump())
    return repo


def test_git_source_skips_legacy_commits(repo_with_events: GitRepo):
    src = GitEventSource(repo_with_events)
    events = src.read(limit=10)
    assert len(events) == 3  # legacy commit dropped
    assert all(isinstance(e, EventRecord) for e in events)


def test_git_source_filter_by_type(repo_with_events: GitRepo):
    src = GitEventSource(repo_with_events)
    events = src.read(types=[EventType.TASK_CLAIMED])
    assert len(events) == 1
    assert events[0].envelope.type == EventType.TASK_CLAIMED


def test_git_source_since_id_excludes_that_commit(repo_with_events: GitRepo):
    src = GitEventSource(repo_with_events)
    all_events = src.read()
    # Pick the middle one as boundary; expect strictly newer events back.
    boundary = all_events[1].source_id
    newer = src.read(since_id=boundary)
    assert len(newer) == 1
    assert newer[0].source_id == all_events[0].source_id


def test_git_source_limit(repo_with_events: GitRepo):
    src = GitEventSource(repo_with_events)
    assert len(src.read(limit=2)) == 2


# ---------------------------------------------------------------------------
# Source replaceability: PLAN's "架构改进 C" verification
# ---------------------------------------------------------------------------


class _MockSource:
    """An EventSource that reads from an in-memory list — zero git involvement."""

    def __init__(self, records: list[EventRecord]):
        self._records = records

    def read(self, *, since_id=None, types=None, limit=100):
        out = list(self._records)
        if types:
            wanted = set(types)
            out = [r for r in out if r.envelope.type in wanted]
        return out[:limit]


def test_read_events_works_against_mock_source():
    records = [
        EventRecord(
            envelope=EventEnvelope(type=EventType.MEMBER_JOINED, actor="bob"),
            source_id="mock-1",
        ),
        EventRecord(
            envelope=EventEnvelope(type=EventType.TASK_CLAIMED, actor="bob", task_id="task-001"),
            source_id="mock-2",
        ),
    ]
    src: EventSource = _MockSource(records)
    out = read_events(src, types=[EventType.TASK_CLAIMED])
    assert len(out) == 1
    assert out[0].source_id == "mock-2"
