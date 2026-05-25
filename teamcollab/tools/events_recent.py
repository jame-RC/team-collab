"""``events_recent``: read recent EventEnvelopes from the local clone.

Thin wrapper over :class:`GitEventSource` + :func:`read_events`. Replaces
SSE / long-polling — callers just ask for "what's new since SHA X" and the
git log gives a deterministic answer.

Always pulls before reading so the local view is current; offline pull is
non-fatal (we still return whatever's in the local clone).
"""
from __future__ import annotations

from pathlib import Path

from teamcollab.contracts import EventType
from teamcollab.events import GitEventSource, read_events
from teamcollab.git_ops import GitRepo, OfflineError


def events_recent(
    *,
    local_path: str | Path,
    since_sha: str | None = None,
    types: list[str] | list[EventType] | None = None,
    limit: int = 50,
) -> dict:
    root = Path(local_path).resolve()
    repo = GitRepo(root)

    try:
        repo.pull(branch="main")
    except OfflineError:
        pass

    type_filter: list[EventType] | None = None
    if types:
        type_filter = [EventType(t) if not isinstance(t, EventType) else t for t in types]

    source = GitEventSource(repo)
    records = read_events(
        source,
        since_id=since_sha,
        types=type_filter,
        limit=limit,
    )

    return {
        "events": [
            {
                "source_id": r.source_id,
                "envelope": r.envelope.model_dump(mode="json"),
            }
            for r in records
        ],
        "count": len(records),
    }
