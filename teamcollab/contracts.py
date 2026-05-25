"""Pydantic contracts shared by every MCP tool, the coordinator skill, and GitHub Actions runners.

The single source of truth for what gets serialized into the repo (tasks/, artifacts/, reviews/,
glossary.json, project.json, .teamcollab/members.json) and into commit messages
(via :class:`EventEnvelope`).
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = 1


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Domain enums
# ---------------------------------------------------------------------------


class OutputType(str, Enum):
    MARKDOWN = "markdown"
    CODE = "code"
    MIXED = "mixed"
    SLIDES = "slides"


class TaskStatus(str, Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    REJECTED = "rejected"


class Verdict(str, Enum):
    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    REJECTED = "rejected"


class Role(str, Enum):
    LEADER = "leader"
    MEMBER = "member"


class EventType(str, Enum):
    PROJECT_CREATED = "project_created"
    MEMBER_JOINED = "member_joined"
    TASKS_DEFINED = "tasks_defined"
    TASK_ADDED = "task_added"
    TASK_CLAIMED = "task_claimed"
    ARTIFACT_SUBMITTED = "artifact_submitted"
    REVIEW_POSTED = "review_posted"
    GLOSSARY_UPDATED = "glossary_updated"
    FINAL_INTEGRATED = "final_integrated"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Project / membership
# ---------------------------------------------------------------------------


class MemberInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    role: Role = Role.MEMBER
    capabilities: list[str] = Field(default_factory=list)
    joined_at: datetime = Field(default_factory=_utcnow)


class ProjectMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    brief: str
    deadline: datetime | None = None
    members: list[MemberInfo] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)
    repo_url: str | None = None
    schema_version: int = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


class TaskContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(pattern=r"^task-\d{3,}$")
    title: str
    brief: str = ""
    deps: list[str] = Field(default_factory=list)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    owner: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=_utcnow)
    claimed_at: datetime | None = None
    submitted_at: datetime | None = None
    schema_version: int = SCHEMA_VERSION

    @field_validator("deps")
    @classmethod
    def _no_self_loop(cls, deps: list[str], info) -> list[str]:
        tid = info.data.get("task_id")
        if tid and tid in deps:
            raise ValueError(f"task {tid} cannot depend on itself")
        return deps


# ---------------------------------------------------------------------------
# Artifacts and reviews
# ---------------------------------------------------------------------------


class Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    actor: str
    content_path: str
    refs: list[str] = Field(default_factory=list)
    submitted_at: datetime = Field(default_factory=_utcnow)
    schema_version: int = SCHEMA_VERSION


class ReviewComment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locator: str = ""
    severity: Literal["info", "minor", "major", "blocker"] = "minor"
    message: str


class ReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    verdict: Verdict
    score: int = Field(ge=0, le=100)
    comments: list[ReviewComment] = Field(default_factory=list)
    reviewer: str
    reviewed_at: datetime = Field(default_factory=_utcnow)
    schema_version: int = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Glossary
# ---------------------------------------------------------------------------


class GlossaryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str
    definition: str
    aliases: list[str] = Field(default_factory=list)
    updated_by: str
    updated_at: datetime = Field(default_factory=_utcnow)


class Glossary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: dict[str, GlossaryEntry] = Field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION


# ---------------------------------------------------------------------------
# EventEnvelope --- the wire format for "git as event bus"
# ---------------------------------------------------------------------------

_HEADER_LINE = "[teamcollab]"
_TRAILER = "---"


class EventEnvelope(BaseModel):
    """Structured event embedded in commit messages.

    Wire format::

        [teamcollab] <type>
        ---
        type: artifact_submitted
        task_id: task-001
        actor: bob
        schema_version: 1
        ts: 2026-05-24T03:11:00Z
        ---
        free-form human description (optional)
    """

    model_config = ConfigDict(extra="forbid")

    type: EventType
    task_id: str | None = None
    actor: str
    ts: datetime = Field(default_factory=_utcnow)
    schema_version: int = SCHEMA_VERSION
    extra: dict[str, Any] = Field(default_factory=dict)

    def dump(self, description: str = "") -> str:
        header = f"{_HEADER_LINE} {self.type.value}"
        body: dict[str, Any] = {
            "type": self.type.value,
            "actor": self.actor,
            "ts": self.ts.isoformat(),
            "schema_version": self.schema_version,
        }
        if self.task_id is not None:
            body["task_id"] = self.task_id
        if self.extra:
            body["extra"] = self.extra
        yaml_block = yaml.safe_dump(body, sort_keys=False, allow_unicode=True).strip()
        parts = [header, _TRAILER, yaml_block, _TRAILER]
        if description:
            parts.append(description.rstrip())
        return "\n".join(parts) + "\n"

    @classmethod
    def parse(cls, commit_message: str) -> Self | None:
        """Return None for legacy/non-envelope commits rather than raising."""
        lines = commit_message.splitlines()
        if not lines or not lines[0].startswith(_HEADER_LINE):
            return None
        try:
            first = lines.index(_TRAILER, 1)
            second = lines.index(_TRAILER, first + 1)
        except ValueError:
            return None
        yaml_text = "\n".join(lines[first + 1 : second])
        try:
            data = yaml.safe_load(yaml_text) or {}
        except yaml.YAMLError:
            return None
        if not isinstance(data, dict) or "type" not in data:
            return None
        try:
            return cls.model_validate(data)
        except Exception:
            return None
