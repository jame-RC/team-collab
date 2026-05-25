"""MCP stdio server entry — exposes the teamcollab tools via FastMCP.

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

import json
import os
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
from teamcollab.tools._resolve import ProjectNotFoundError, resolve_project_root
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

os.environ.setdefault("TEAMCOLLAB_PROJECT_ROOT", os.getcwd())

mcp = FastMCP("teamcollab")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve(local_path: str | None) -> str:
    """Resolve project root — returns string path for downstream tools."""
    root = resolve_project_root(local_path)
    return str(root)


def _err(code: str, message: str, **payload: Any) -> dict:
    """Standard tool-level error envelope."""
    return {"error": {"code": code, "message": message, **payload}}


# ---------------------------------------------------------------------------
# team_init / team_join
# ---------------------------------------------------------------------------


@mcp.tool()
def team_init(
    title: str,
    brief: str,
    leader: str,
    local_path: str | None = None,
    leader_capabilities: list[str] | None = None,
    deadline: str | None = None,
    remote_url: str | None = None,
) -> dict:
    """Bootstrap a new team-collab project.

    If ``local_path`` is omitted, uses the auto-detected project root or CWD.
    Writes ``project.json`` / ``members.json`` / ``glossary.json`` / Actions
    workflow + ``.gitignore`` and commits them. If ``remote_url`` is provided,
    the initial commit is pushed; otherwise the repo stays local-only.
    """
    resolved = local_path or os.getcwd()
    return _team_init(
        local_path=resolved,
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
    name: str,
    local_path: str | None = None,
    role: Role = Role.MEMBER,
    capabilities: list[str] | None = None,
) -> dict:
    """Clone the project repo and add ``name`` to members.json.

    If ``local_path`` is omitted, clones into a subdirectory of CWD.
    """
    resolved = local_path or os.path.join(os.getcwd(), name + "-project")
    return _team_join(
        remote_url=remote_url,
        local_path=resolved,
        name=name,
        role=role,
        capabilities=capabilities,
    )


# ---------------------------------------------------------------------------
# task_create_batch / task_add — leader-side task definition
# ---------------------------------------------------------------------------


@mcp.tool()
def task_create_batch(
    tasks: list[TaskContract],
    actor: str,
    local_path: str | None = None,
) -> dict:
    """Validate the DAG and write all ``tasks`` in a single commit.

    Rejects cycles, dangling deps, duplicate task_ids, and unknown owners.
    """
    try:
        return _task_create_batch(local_path=_resolve(local_path), tasks=tasks, actor=actor)
    except DagError as e:
        return _err(e.code, str(e), **e.payload)


@mcp.tool()
def task_add(
    task: TaskContract,
    actor: str,
    local_path: str | None = None,
) -> dict:
    """Append a single task — same validation as ``task_create_batch``, one item."""
    try:
        return _task_add(local_path=_resolve(local_path), task=task, actor=actor)
    except DagError as e:
        return _err(e.code, str(e), **e.payload)


# ---------------------------------------------------------------------------
# task_list / task_claim / task_submit / task_review / read_artifact
# ---------------------------------------------------------------------------


@mcp.tool()
def task_list(
    filter: str = "all",
    me: str | None = None,
    tree: bool = False,
    local_path: str | None = None,
) -> dict:
    """Read the task DAG. ``filter`` is ``all`` | ``available`` | ``blocked`` | ``mine``."""
    return _task_list(local_path=_resolve(local_path), filter=filter, me=me, tree=tree)  # type: ignore[arg-type]


@mcp.tool()
def task_claim(task_id: str, me: str, local_path: str | None = None) -> dict:
    """Claim ``task_id`` for ``me``. Fails if deps aren't approved or task isn't pending."""
    try:
        return _task_claim(local_path=_resolve(local_path), task_id=task_id, me=me)
    except TaskClaimError as e:
        return _err(e.code, str(e), **e.payload)


@mcp.tool()
def task_submit(
    task_id: str,
    me: str,
    content: str,
    refs: list[str] | None = None,
    files: list[str] | None = None,
    local_path: str | None = None,
) -> dict:
    """Write the artifact under ``artifacts/<me>/<task_id>/`` and mark task submitted.

    ``files`` is an optional list of absolute paths to additional files (code, data,
    attachments) to include alongside the main content.md document.
    """
    try:
        return _task_submit(
            local_path=_resolve(local_path),
            task_id=task_id,
            me=me,
            content=content,
            refs=refs,
            files=files,
        )
    except TaskSubmitError as e:
        return _err(e.code, str(e), **e.payload)


@mcp.tool()
def task_review(
    task_id: str,
    reviewer: str,
    verdict: Verdict,
    score: int,
    comments: list[dict] | None = None,
    local_path: str | None = None,
) -> dict:
    """Post a review for ``task_id``; updates task status per ``verdict``."""
    return _task_review(
        local_path=_resolve(local_path),
        task_id=task_id,
        reviewer=reviewer,
        verdict=verdict,
        score=score,
        comments=comments,
    )


@mcp.tool()
def read_artifact(member: str, task_id: str, local_path: str | None = None) -> dict:
    """Read ``artifacts/<member>/<task_id>/{content.md, meta.json}`` from the local clone."""
    try:
        return _read_artifact(local_path=_resolve(local_path), member=member, task_id=task_id)
    except ArtifactNotFoundError as e:
        return _err(e.code, str(e), **e.payload)


# ---------------------------------------------------------------------------
# search_blackboard / glossary / events / sync
# ---------------------------------------------------------------------------


@mcp.tool()
def search_blackboard(
    query: str,
    top_k: int = 10,
    semantic: bool = False,
    local_path: str | None = None,
) -> dict:
    """``git grep`` across the local clone, with optional fastembed semantic fallback."""
    return _search_blackboard(
        local_path=_resolve(local_path),
        query=query,
        top_k=top_k,
        semantic=semantic,
    )


@mcp.tool()
def glossary_get(term: str | None = None, local_path: str | None = None) -> dict:
    """Return the full glossary, or just one ``term`` if provided."""
    return _glossary_get(local_path=_resolve(local_path), term=term)


@mcp.tool()
def glossary_update(
    term: str,
    definition: str,
    actor: str,
    aliases: list[str] | None = None,
    local_path: str | None = None,
) -> dict:
    """Upsert one glossary entry. Uses pull-modify-push retry to survive concurrent edits."""
    return _glossary_update(
        local_path=_resolve(local_path),
        term=term,
        definition=definition,
        actor=actor,
        aliases=aliases,
    )


@mcp.tool()
def events_recent(
    since_sha: str | None = None,
    types: list[EventType] | None = None,
    limit: int = 50,
    local_path: str | None = None,
) -> dict:
    """Replay recent EventEnvelope-bearing commits, optionally filtered by ``types``."""
    return _events_recent(
        local_path=_resolve(local_path),
        since_sha=since_sha,
        types=types,
        limit=limit,
    )


@mcp.tool()
def sync_now(local_path: str | None = None) -> dict:
    """Explicit pull-then-push. Offline failures are reported, not raised."""
    return _sync_now(local_path=_resolve(local_path))


# ---------------------------------------------------------------------------
# generate_slides — PPT generation from markdown outline
# ---------------------------------------------------------------------------


@mcp.tool()
def generate_slides(
    outline: str,
    task_id: str,
    me: str,
    format: str = "pptx",
    local_path: str | None = None,
) -> dict:
    """Generate a presentation from a Markdown outline.

    ``format`` can be ``pptx`` (generates .pptx file) or ``markdown`` (returns structured outline).
    The outline uses H1 (``# Title``) for each slide, bullets for content,
    and blockquotes (``>``) for speaker notes.
    """
    from teamcollab.tools._slides import SlidesError, generate_pptx, outline_to_markdown_slides

    if format == "markdown":
        return {"task_id": task_id, "format": "markdown", "content": outline_to_markdown_slides(outline)}

    try:
        root = Path(_resolve(local_path))
    except ProjectNotFoundError:
        return _err("NO_PROJECT", "No TeamCollab project found.")

    from teamcollab.tools._paths import artifact_dir
    out_dir = artifact_dir(root, me, task_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "slides.pptx"

    try:
        generate_pptx(outline, out_path)
    except SlidesError as e:
        return _err(e.code, str(e))

    return {
        "task_id": task_id,
        "format": "pptx",
        "path": str(out_path.relative_to(root)),
    }


# ---------------------------------------------------------------------------
# get_project_context — zero-arg status summary
# ---------------------------------------------------------------------------


@mcp.tool()
def get_project_context(local_path: str | None = None) -> dict:
    """Return a summary of the current TeamCollab project state.

    Includes project metadata, member list, task statistics, and recent events.
    Useful for AI to understand the current context without multiple tool calls.
    """
    try:
        root = Path(_resolve(local_path))
    except ProjectNotFoundError:
        return _err("NO_PROJECT", "No TeamCollab project found in current directory.")

    from teamcollab.tools._paths import (
        glossary_json,
        members_json,
        project_json,
        tasks_dir,
    )
    from teamcollab.tools._io import read_json

    result: dict[str, Any] = {"project_root": str(root)}

    proj_file = project_json(root)
    if proj_file.exists():
        result["project"] = read_json(proj_file)

    mem_file = members_json(root)
    if mem_file.exists():
        result["members"] = read_json(mem_file)

    t_dir = tasks_dir(root)
    if t_dir.exists():
        tasks = []
        for tf in sorted(t_dir.glob("*.json")):
            tasks.append(read_json(tf))
        result["tasks"] = tasks
        result["task_stats"] = {
            "total": len(tasks),
            "pending": sum(1 for t in tasks if t.get("status") == "pending"),
            "in_progress": sum(1 for t in tasks if t.get("status") == "in_progress"),
            "submitted": sum(1 for t in tasks if t.get("status") == "submitted"),
            "approved": sum(1 for t in tasks if t.get("status") == "approved"),
        }

    glos_file = glossary_json(root)
    if glos_file.exists():
        glos = read_json(glos_file)
        result["glossary_term_count"] = len(glos.get("entries", {}))

    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """stdio transport — invoked by ``teamcollab-server`` console script and by
    Claude Code when the plugin's ``mcpServers`` block spawns this process."""
    mcp.run()


if __name__ == "__main__":
    main()
