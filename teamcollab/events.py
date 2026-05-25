"""Event abstraction layer.

The whole point: upstream code (coordinator skill, MCP tools) reads events via
:func:`read_events` and never touches ``git log`` directly. Today the source is
git commit messages parsed via :class:`EventEnvelope`. Tomorrow it could be a
GitHub Webhook bridge, NATS, Kafka — swap :class:`GitEventSource` for another
:class:`EventSource` implementation and nothing else changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Protocol

from teamcollab.contracts import EventEnvelope, EventType
from teamcollab.git_ops import GitRepo


@dataclass
class EventRecord:
    """A parsed envelope plus the source identifier (e.g. commit SHA)."""

    envelope: EventEnvelope
    source_id: str  # commit SHA for git source; opaque otherwise


class EventSource(Protocol):
    """Anything that can yield :class:`EventRecord` instances on demand."""

    def read(
        self,
        *,
        since_id: str | None = None,
        types: Iterable[EventType] | None = None,
        limit: int = 100,
    ) -> list[EventRecord]:
        ...


class GitEventSource:
    """Reads events from a local git clone's commit history.

    Newest-first by default (matches ``git log`` semantics). Commits whose
    message is not a valid :class:`EventEnvelope` are silently skipped — this
    lets the system tolerate hand-made commits sitting next to bot commits.
    """

    def __init__(self, repo: GitRepo):
        self._repo = repo

    def read(
        self,
        *,
        since_id: str | None = None,
        types: Iterable[EventType] | None = None,
        limit: int = 100,
    ) -> list[EventRecord]:
        commits = self._repo.log(max_count=limit, since_sha=since_id)
        wanted = set(types) if types else None
        out: list[EventRecord] = []
        for c in commits:
            envelope = EventEnvelope.parse(c.message)
            if envelope is None:
                continue
            if wanted is not None and envelope.type not in wanted:
                continue
            out.append(EventRecord(envelope=envelope, source_id=c.sha))
        return out


def read_events(
    source: EventSource,
    *,
    since_id: str | None = None,
    types: Iterable[EventType] | None = None,
    limit: int = 100,
) -> list[EventRecord]:
    """Public entrypoint. Thin wrapper so callers depend on the function, not the class."""
    return source.read(since_id=since_id, types=types, limit=limit)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
