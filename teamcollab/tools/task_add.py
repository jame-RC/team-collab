"""``task_add``: append one task to an already-bootstrapped project.

For mid-project additions (a leader realizes a sub-step was missing).
Same validation surface as :func:`task_create_batch`, just for one task.
Writes a single ``tasks/<task_id>.json`` and emits an
``EventEnvelope(type=task_added)`` commit.
"""
from __future__ import annotations

from pathlib import Path

from teamcollab.contracts import EventEnvelope, EventType, TaskContract
from teamcollab.git_ops import GitRepo, OfflineError
from teamcollab.tools import _paths
from teamcollab.tools._dag import validate_and_warn
from teamcollab.tools._io import write_model
from teamcollab.tools.task_create_batch import _load_existing_tasks, _load_member_names


def task_add(
    *,
    local_path: str | Path,
    task: TaskContract,
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
        [task],
        existing_tasks=existing,
        member_names=members,
    )

    p = _paths.task_json(root, task.task_id)
    write_model(p, task)
    repo.add([p])

    env = EventEnvelope(type=EventType.TASK_ADDED, actor=actor, task_id=task.task_id)
    sha = repo.commit(env.dump(f"added task {task.task_id}: {task.title}"))

    pushed = False
    if sha:
        try:
            repo.push(branch="main")
            pushed = True
        except OfflineError:
            pushed = False

    return {
        "sha": sha,
        "warnings": warnings,
        "pushed": pushed,
        "task_id": task.task_id,
    }
