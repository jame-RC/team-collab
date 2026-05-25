"""``task_list``: read the task DAG out of the local clone.

Filters:

* ``all`` — every task on disk.
* ``available`` — ``status == pending``, owner unset, AND every dep has
  ``status == approved``. These are tasks an idle member can claim right now.
* ``blocked`` — ``status == pending`` but at least one dep is not yet
  approved. Each entry is annotated with ``waiting_for`` so the caller can
  tell the user which upstream tasks they're waiting on.
* ``mine`` — owned by the requesting member, regardless of status.

Pulls before reading so the local snapshot is current. Offline pull is
non-fatal (we read whatever the local clone has).

If ``tree=True`` we also return an ASCII rendering of the DAG — handy for
``/team-status`` output and for the validation step.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from teamcollab.contracts import TaskContract, TaskStatus
from teamcollab.git_ops import GitRepo, OfflineError
from teamcollab.tools import _paths
from teamcollab.tools._io import read_model

Filter = Literal["all", "available", "blocked", "mine"]


def _load_all(root: Path) -> dict[str, TaskContract]:
    tdir = _paths.tasks_dir(root)
    out: dict[str, TaskContract] = {}
    if not tdir.exists():
        return out
    for p in sorted(tdir.glob("task-*.json")):
        t = read_model(p, TaskContract)
        out[t.task_id] = t
    return out


def _waiting_for(task: TaskContract, all_tasks: dict[str, TaskContract]) -> list[str]:
    return [
        d
        for d in task.deps
        if d not in all_tasks or all_tasks[d].status != TaskStatus.APPROVED
    ]


def _render_tree(tasks: dict[str, TaskContract]) -> str:
    """Compact ASCII DAG: roots first, then children indented under their dep."""
    children: dict[str, list[str]] = {tid: [] for tid in tasks}
    for tid, t in tasks.items():
        for d in t.deps:
            if d in children:
                children[d].append(tid)

    roots = sorted(tid for tid, t in tasks.items() if not t.deps)
    seen: set[str] = set()
    lines: list[str] = []

    def walk(tid: str, depth: int) -> None:
        if tid in seen:
            lines.append("  " * depth + f"- {tid} (cycle)")
            return
        seen.add(tid)
        t = tasks[tid]
        owner = t.owner or "?"
        lines.append("  " * depth + f"- {tid} [{t.status.value}] @{owner} — {t.title}")
        for c in sorted(children.get(tid, [])):
            walk(c, depth + 1)

    for r in roots:
        walk(r, 0)

    leftover = sorted(set(tasks) - seen)
    for tid in leftover:
        walk(tid, 0)

    return "\n".join(lines)


def task_list(
    *,
    local_path: str | Path,
    filter: Filter = "all",
    me: str | None = None,
    tree: bool = False,
) -> dict:
    root = Path(local_path).resolve()
    repo = GitRepo(root)
    try:
        repo.pull(branch="main")
    except OfflineError:
        pass

    all_tasks = _load_all(root)

    items: list[dict] = []
    for tid in sorted(all_tasks):
        t = all_tasks[tid]
        waiting = _waiting_for(t, all_tasks)

        if filter == "available":
            if t.status != TaskStatus.PENDING or waiting:
                continue
        elif filter == "blocked":
            if t.status != TaskStatus.PENDING or not waiting:
                continue
        elif filter == "mine":
            if me is None or t.owner != me:
                continue

        entry = t.model_dump(mode="json")
        entry["waiting_for"] = waiting
        items.append(entry)

    out: dict = {"tasks": items, "count": len(items)}
    if tree:
        out["tree"] = _render_tree(all_tasks)
    return out
