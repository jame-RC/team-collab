"""``task_create_batch``: write a leader-defined task list into the repo.

Critically, this tool does **not** decompose the leader's brief — the
coordinator skill does that conversationally and hands a finished list of
:class:`TaskContract` instances to this tool. Here we only:

1. Pull latest state.
2. Hard-validate via :mod:`teamcollab.tools._dag` (cycles, unknown deps,
   dup task_id, owner not in members) — failures raise :class:`DagError`.
3. Collect any soft warnings (bottleneck, orphan, overload).
4. Write each ``tasks/<task_id>.json``.
5. Single commit with :class:`EventEnvelope` of type ``tasks_defined``.
6. Push (offline-tolerated).

The single-commit-per-batch policy keeps git history readable: one human
"defined the task list" action == one commit.
"""
from __future__ import annotations

from pathlib import Path

from teamcollab.contracts import EventEnvelope, EventType, ProjectMeta, TaskContract
from teamcollab.git_ops import GitRepo, OfflineError
from teamcollab.tools import _paths
from teamcollab.tools._dag import validate_and_warn
from teamcollab.tools._io import read_json, read_model, write_model


def _load_existing_tasks(root: Path) -> list[TaskContract]:
    out: list[TaskContract] = []
    tdir = _paths.tasks_dir(root)
    if not tdir.exists():
        return out
    for p in sorted(tdir.glob("task-*.json")):
        out.append(read_model(p, TaskContract))
    return out


def _load_member_names(root: Path) -> list[str]:
    mp = _paths.members_json(root)
    if mp.exists():
        raw = read_json(mp)
        if isinstance(raw, list):
            return [m["name"] for m in raw if isinstance(m, dict) and "name" in m]
    pp = _paths.project_json(root)
    if pp.exists():
        project = read_model(pp, ProjectMeta)
        return [m.name for m in project.members]
    return []


def task_create_batch(
    *,
    local_path: str | Path,
    tasks: list[TaskContract],
    actor: str,
) -> dict:
    root = Path(local_path).resolve()
    repo = GitRepo(root)

    try:
        repo.pull(branch="main")
    except OfflineError:
        pass

    existing = _load_existing_tasks(root)
    members = _load_member_names(root)

    warnings = validate_and_warn(
        list(tasks),
        existing_tasks=existing,
        member_names=members,
    )

    written_paths: list[Path] = []
    for t in tasks:
        p = _paths.task_json(root, t.task_id)
        write_model(p, t)
        written_paths.append(p)

    if not written_paths:
        return {"shas": [], "warnings": warnings, "pushed": True, "task_ids": []}

    repo.add(written_paths)
    env = EventEnvelope(type=EventType.TASKS_DEFINED, actor=actor)
    description = f"defined {len(tasks)} task(s): {', '.join(t.task_id for t in tasks)}"
    sha = repo.commit(env.dump(description))

    pushed = False
    if sha:
        try:
            repo.push(branch="main")
            pushed = True
        except OfflineError:
            pushed = False

    return {
        "shas": [sha] if sha else [],
        "warnings": warnings,
        "pushed": pushed,
        "task_ids": [t.task_id for t in tasks],
    }
