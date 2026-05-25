"""MCP stdio server entry — exposes the 14 teamcollab tools via FastMCP.

Each tool is a thin wrapper that re-exposes the underlying ``teamcollab.tools.*``
callable with the same parameters. We register wrappers (not the raw callables)
so FastMCP sees explicit parameter signatures with Pydantic-friendly types and
so we can normalise return values (Pydantic models / Path objects) into JSON
before they hit the wire.

The whole module is built around two principles:

1. **No business logic here.** The tools live in ``teamcollab.tools.*``;
   this module only adapts them to the MCP protocol.
2. **Errors are returned, not raised.** Tool functions raise structured
   exceptions (``TaskClaimError``, ``DagError``, etc.). We catch them and
   return ``{"error": {...}}`` so the MCP client sees a tool-level failure
   rather than a transport crash.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from teamcollab.contracts import (
    EventType,
    Role,
    TaskContract,
    Verdict,
)
from teamcollab.tools._dag import DagError
from teamcollab.tools.read_artifact import ArtifactNotFoundError
from teamcollab.tools.task_claim import TaskClaimError
from teamcollab.tools.task_submit import TaskSubmitError
from teamcollab.tools import (
    events_recent as _events_recent,
    glossary_get as _glossary_get,
    glossary_update as _glossary_update,
    read_artifact as _read_artifact,
    search_blackboard as _search_blackboard,
    sync_now as _sync_now,
    task_add as _task_add,
    task_claim as _task_claim,
    task_create_batch as _task_create_batch,
    task_list as _task_list,
    task_review as _task_review,
    task_submit as _task_submit,
    team_init as _team_init,
    team_join as _team_join,
)

mcp = FastMCP("teamcollab")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _err(code: str, message: str, **payload: Any) -> dict:
    """Standard tool-level error envelope."""
    return {"error": {"code": code, "message": message, **payload}}


# ---------------------------------------------------------------------------
# team_init / team_join
# ---------------------------------------------------------------------------


@mcp.tool()
def team_init(
    local_path: str,
    title: str,
    brief: str,
    leader: str,
    leader_capabilities: list[str] | None = None,
    deadline: str | None = None,
    remote_url: str | None = None,
) -> dict:
    """Bootstrap a new team-collab project at ``local_path``.

    Writes ``project.json`` / ``members.json`` / ``glossary.json`` / Actions
    workflow + ``.gitignore`` and commits them. If ``remote_url`` is provided,
    the initial commit is pushed; otherwise the repo stays local-only.
    """
    return _team_init(
        local_path=local_path,
        title=title,
        brief=brief,
        leader=leader,
        leader_capabilities=leader_capabilities,
        deadline=deadline,
        remote_url=remote_url,
    )


@mcp.tool()
def team_join(
    remote_url: str,
    local_path: str,
    name: str,
    role: Role = Role.MEMBER,
    capabilities: list[str] | None = None,
) -> dict:
    """Clone the project repo (if not already present) and add ``name`` to members.json."""
    return _team_join(
        remote_url=remote_url,
        local_path=local_path,
        name=name,
        role=role,
        capabilities=capabilities,
    )


# ---------------------------------------------------------------------------
# task_create_batch / task_add — leader-side task definition
# ---------------------------------------------------------------------------


@mcp.tool()
def task_create_batch(
    local_path: str,
    tasks: list[TaskContract],
    actor: str,
) -> dict:
    """Validate the DAG and write all ``tasks`` in a single commit.

    Rejects cycles, dangling deps, duplicate task_ids, and unknown owners.
    """
    try:
        return _task_create_batch(local_path=local_path, tasks=tasks, actor=actor)
    except DagError as e:
        return _err(e.code, str(e), **e.payload)


@mcp.tool()
def task_add(
    local_path: str,
    task: TaskContract,
    actor: str,
) -> dict:
    """Append a single task — same validation as ``task_create_batch``, one item."""
    try:
        return _task_add(local_path=local_path, task=task, actor=actor)
    except DagError as e:
        return _err(e.code, str(e), **e.payload)


# ---------------------------------------------------------------------------
# task_list / task_claim / task_submit / task_review / read_artifact
# ---------------------------------------------------------------------------


@mcp.tool()
def task_list(
    local_path: str,
    filter: str = "all",
    me: str | None = None,
    tree: bool = False,
) -> dict:
    """Read the task DAG. ``filter`` is ``all`` | ``available`` | ``blocked`` | ``mine``."""
    return _task_list(local_path=local_path, filter=filter, me=me, tree=tree)  # type: ignore[arg-type]


@mcp.tool()
def task_claim(local_path: str, task_id: str, me: str) -> dict:
    """Claim ``task_id`` for ``me``. Fails if deps aren't approved or task isn't pending."""
    try:
        return _task_claim(local_path=local_path, task_id=task_id, me=me)
    except TaskClaimError as e:
        return _err(e.code, str(e), **e.payload)


@mcp.tool()
def task_submit(
    local_path: str,
    task_id: str,
    me: str,
    content: str,
    refs: list[str] | None = None,
) -> dict:
    """Write the artifact under ``artifacts/<me>/<task_id>/`` and mark task submitted."""
    try:
        return _task_submit(
            local_path=local_path,
            task_id=task_id,
            me=me,
            content=content,
            refs=refs,
        )
    except TaskSubmitError as e:
        return _err(e.code, str(e), **e.payload)


@mcp.tool()
def task_review(
    local_path: str,
    task_id: str,
    reviewer: str,
    verdict: Verdict,
    score: int,
    comments: list[dict] | None = None,
) -> dict:
    """Post a review for ``task_id``; updates task status per ``verdict``."""
    return _task_review(
        local_path=local_path,
        task_id=task_id,
        reviewer=reviewer,
        verdict=verdict,
        score=score,
        comments=comments,
    )


@mcp.tool()
def read_artifact(local_path: str, member: str, task_id: str) -> dict:
    """Read ``artifacts/<member>/<task_id>/{content.md, meta.json}`` from the local clone."""
    try:
        return _read_artifact(local_path=local_path, member=member, task_id=task_id)
    except ArtifactNotFoundError as e:
        return _err(e.code, str(e), **e.payload)


# ---------------------------------------------------------------------------
# search_blackboard / glossary / events / sync
# ---------------------------------------------------------------------------


@mcp.tool()
def search_blackboard(
    local_path: str,
    query: str,
    top_k: int = 10,
    semantic: bool = False,
) -> dict:
    """``git grep`` across the local clone, with optional fastembed semantic fallback."""
    return _search_blackboard(
        local_path=local_path,
        query=query,
        top_k=top_k,
        semantic=semantic,
    )


@mcp.tool()
def glossary_get(local_path: str, term: str | None = None) -> dict:
    """Return the full glossary, or just one ``term`` if provided."""
    return _glossary_get(local_path=local_path, term=term)


@mcp.tool()
def glossary_update(
    local_path: str,
    term: str,
    definition: str,
    actor: str,
    aliases: list[str] | None = None,
) -> dict:
    """Upsert one glossary entry. Uses pull-modify-push retry to survive concurrent edits."""
    return _glossary_update(
        local_path=local_path,
        term=term,
        definition=definition,
        actor=actor,
        aliases=aliases,
    )


@mcp.tool()
def events_recent(
    local_path: str,
    since_sha: str | None = None,
    types: list[EventType] | None = None,
    limit: int = 50,
) -> dict:
    """Replay recent EventEnvelope-bearing commits, optionally filtered by ``types``."""
    return _events_recent(
        local_path=local_path,
        since_sha=since_sha,
        types=types,
        limit=limit,
    )


@mcp.tool()
def sync_now(local_path: str) -> dict:
    """Explicit pull-then-push. Offline failures are reported, not raised."""
    return _sync_now(local_path=local_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """stdio transport — invoked by ``teamcollab-server`` console script and by
    Claude Code when the plugin's ``mcpServers`` block spawns this process."""
    mcp.run()


if __name__ == "__main__":
    main()
