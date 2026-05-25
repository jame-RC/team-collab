"""``glossary_get`` and ``glossary_update``: shared term dictionary.

The glossary is the *one* file in the repo where multiple members can write
concurrently — they all share a single ``glossary.json``. We therefore route
writes through :func:`with_pull_modify_push_retry` so concurrent updates
merge semantically rather than fighting over textual diffs.

* ``glossary_get`` is a pure read: pull (offline-tolerated) → return the
  parsed :class:`Glossary` plus the requested term if asked.
* ``glossary_update`` upserts a single term. The ``modify_fn`` captures the
  *intent* (``set entries[term] = …``) so each retry re-reads the latest
  state and applies the same semantic mutation — never an out-of-date diff.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from teamcollab.conflict import with_pull_modify_push_retry
from teamcollab.contracts import (
    EventEnvelope,
    EventType,
    Glossary,
    GlossaryEntry,
)
from teamcollab.git_ops import GitRepo, OfflineError
from teamcollab.tools import _paths
from teamcollab.tools._io import read_model, read_model_or_default, write_model


def glossary_get(
    *,
    local_path: str | Path,
    term: str | None = None,
) -> dict:
    root = Path(local_path).resolve()
    repo = GitRepo(root)
    try:
        repo.pull(branch="main")
    except OfflineError:
        pass

    g_path = _paths.glossary_json(root)
    glossary = read_model_or_default(g_path, Glossary, Glossary())

    out: dict = {
        "entries": {k: v.model_dump(mode="json") for k, v in glossary.entries.items()},
        "count": len(glossary.entries),
    }
    if term is not None:
        entry = glossary.entries.get(term)
        out["term"] = term
        out["entry"] = entry.model_dump(mode="json") if entry else None
    return out


def glossary_update(
    *,
    local_path: str | Path,
    term: str,
    definition: str,
    actor: str,
    aliases: list[str] | None = None,
) -> dict:
    root = Path(local_path).resolve()
    repo = GitRepo(root)
    g_path = _paths.glossary_json(root)

    def _modify(_repo_root: Path):
        # Re-read fresh from disk on every retry — never trust a captured copy.
        glossary = (
            read_model(g_path, Glossary) if g_path.exists() else Glossary()
        )
        entry = GlossaryEntry(
            term=term,
            definition=definition,
            aliases=aliases or [],
            updated_by=actor,
            updated_at=datetime.now(timezone.utc),
        )
        glossary.entries[term] = entry
        write_model(g_path, glossary)
        return [g_path]

    env = EventEnvelope(type=EventType.GLOSSARY_UPDATED, actor=actor)
    result = with_pull_modify_push_retry(
        repo,
        _modify,
        commit_message=env.dump(f"{actor} updated glossary[{term}]"),
        branch="main",
    )

    return {
        "term": term,
        "sha": result.sha,
        "attempts": result.attempts,
        "pushed": result.pushed,
    }
