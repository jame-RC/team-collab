"""Tests for teamcollab.contracts."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from teamcollab.contracts import (
    Artifact,
    EventEnvelope,
    EventType,
    Glossary,
    GlossaryEntry,
    MemberInfo,
    ProjectMeta,
    ReviewComment,
    ReviewResult,
    Role,
    TaskContract,
    TaskStatus,
    Verdict,
)


# ---------------------------------------------------------------------------
# EventEnvelope: the wire format must roundtrip cleanly
# ---------------------------------------------------------------------------


class TestEventEnvelopeRoundtrip:
    def test_minimal_envelope_roundtrips(self):
        original = EventEnvelope(
            type=EventType.TASK_CLAIMED,
            task_id="task-001",
            actor="bob",
            ts=datetime(2026, 5, 24, 3, 11, 0, tzinfo=timezone.utc),
        )
        wire = original.dump()
        parsed = EventEnvelope.parse(wire)
        assert parsed is not None
        assert parsed.type == original.type
        assert parsed.task_id == original.task_id
        assert parsed.actor == original.actor
        assert parsed.ts == original.ts
        assert parsed.schema_version == original.schema_version

    def test_envelope_with_description_roundtrips(self):
        original = EventEnvelope(
            type=EventType.ARTIFACT_SUBMITTED,
            task_id="task-002",
            actor="alice",
        )
        wire = original.dump(description="Bob finished the literature review.")
        parsed = EventEnvelope.parse(wire)
        assert parsed is not None
        assert parsed.type == EventType.ARTIFACT_SUBMITTED

    def test_envelope_without_task_id(self):
        original = EventEnvelope(type=EventType.PROJECT_CREATED, actor="alice")
        wire = original.dump()
        parsed = EventEnvelope.parse(wire)
        assert parsed is not None
        assert parsed.task_id is None
        assert parsed.type == EventType.PROJECT_CREATED

    def test_envelope_with_extra(self):
        original = EventEnvelope(
            type=EventType.TASKS_DEFINED,
            actor="alice",
            extra={"task_count": 5, "topology": "hybrid"},
        )
        wire = original.dump()
        parsed = EventEnvelope.parse(wire)
        assert parsed is not None
        assert parsed.extra == {"task_count": 5, "topology": "hybrid"}

    def test_envelope_header_format(self):
        envelope = EventEnvelope(type=EventType.REVIEW_POSTED, actor="alice")
        wire = envelope.dump()
        first_line = wire.splitlines()[0]
        assert first_line == "[teamcollab] review_posted"


class TestEventEnvelopeParseLegacy:
    """parse() must return None (not raise) for non-envelope commits."""

    def test_legacy_plain_commit_returns_none(self):
        assert EventEnvelope.parse("Initial commit") is None

    def test_empty_message_returns_none(self):
        assert EventEnvelope.parse("") is None

    def test_header_without_trailers_returns_none(self):
        assert EventEnvelope.parse("[teamcollab] something\nno trailer here") is None

    def test_malformed_yaml_returns_none(self):
        msg = "[teamcollab] foo\n---\n: : : invalid yaml ::: \n---\n"
        assert EventEnvelope.parse(msg) is None

    def test_yaml_missing_type_returns_none(self):
        msg = "[teamcollab] foo\n---\nactor: bob\n---\n"
        assert EventEnvelope.parse(msg) is None

    def test_unknown_event_type_returns_none(self):
        msg = (
            "[teamcollab] foo\n---\n"
            "type: not_a_real_event\nactor: bob\nts: 2026-05-24T00:00:00+00:00\n"
            "schema_version: 1\n---\n"
        )
        assert EventEnvelope.parse(msg) is None


# ---------------------------------------------------------------------------
# TaskContract validation
# ---------------------------------------------------------------------------


class TestTaskContract:
    def test_valid_task(self):
        t = TaskContract(task_id="task-001", title="Write intro")
        assert t.status == TaskStatus.PENDING
        assert t.deps == []

    def test_self_loop_rejected(self):
        with pytest.raises(ValidationError, match="cannot depend on itself"):
            TaskContract(task_id="task-002", title="t", deps=["task-002"])

    def test_task_id_pattern_enforced(self):
        with pytest.raises(ValidationError):
            TaskContract(task_id="not-a-task", title="t")
        with pytest.raises(ValidationError):
            TaskContract(task_id="task-1", title="t")

    def test_task_id_accepts_three_or_more_digits(self):
        TaskContract(task_id="task-001", title="t")
        TaskContract(task_id="task-9999", title="t")

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            TaskContract(task_id="task-001", title="t", random_field=1)


# ---------------------------------------------------------------------------
# ReviewResult validation
# ---------------------------------------------------------------------------


class TestReviewResult:
    def test_valid_review(self):
        r = ReviewResult(
            task_id="task-001",
            verdict=Verdict.APPROVED,
            score=92,
            reviewer="alice",
        )
        assert r.comments == []

    def test_score_range_enforced(self):
        with pytest.raises(ValidationError):
            ReviewResult(task_id="t", verdict=Verdict.APPROVED, score=-1, reviewer="a")
        with pytest.raises(ValidationError):
            ReviewResult(task_id="t", verdict=Verdict.APPROVED, score=101, reviewer="a")

    def test_severity_literal(self):
        ReviewComment(severity="blocker", message="x")
        with pytest.raises(ValidationError):
            ReviewComment(severity="catastrophic", message="x")


# ---------------------------------------------------------------------------
# Misc smoke: enums, ProjectMeta, Glossary, Artifact
# ---------------------------------------------------------------------------


class TestMisc:
    def test_project_meta_defaults(self):
        p = ProjectMeta(title="Demo", brief="b")
        assert p.members == []
        assert p.schema_version == 1

    def test_member_info_role_default(self):
        m = MemberInfo(name="bob")
        assert m.role == Role.MEMBER

    def test_glossary_roundtrip(self):
        g = Glossary(
            entries={
                "rag": GlossaryEntry(
                    term="RAG",
                    definition="Retrieval Augmented Generation",
                    updated_by="alice",
                )
            }
        )
        dumped = g.model_dump_json()
        restored = Glossary.model_validate_json(dumped)
        assert restored.entries["rag"].term == "RAG"

    def test_artifact_minimal(self):
        a = Artifact(task_id="task-001", actor="bob", content_path="artifacts/bob/task-001/content.md")
        assert a.refs == []
