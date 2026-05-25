"""``task_claim``: a member takes ownership of an available task.

Hard constraints:

* Task must exist.
* Task must be ``pending`` (no stealing in-flight work).
* Every dep must already be ``approved`` — otherwise we return
  ``DEPS_NOT_READY`` with a ``waiting_for`` list so the member knows
  who they're waiting on.

On success: set ``owner=<me>``, ``status=claimed``, ``claimed_at=now``,
write back, commit with ``EventEnvelope(type=task_claimed)``, push.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from teamcollab.contracts import EventEnvelope, EventType, TaskContract, TaskStatus
from teamcollab.git_ops import GitRepo, OfflineError
from teamcollab.tools import _paths
from teamcollab.tools._changelog import log_claim
from teamcollab.tools._io import read_model, write_model
from teamcollab.tools.task_list import _load_all, _waiting_for


class TaskClaimError(RuntimeError):
    """Structured failure surfaced to the coordinator skill."""

    def __init__(self, code: str, message: str, **payload):
        super().__init__(message)
        self.code = code
        self.payload = payload


def task_claim(
    *,
    local_path: str | Path,
    task_id: str,
    me: str,
) -> dict:
    root = Path(local_path).resolve()
    repo = GitRepo(root)

    try:
        repo.pull(branch="main")
    except OfflineError:
        pass

    task_path = _paths.task_json(root, task_id)
    if not task_path.exists():
        raise TaskClaimError("TASK_NOT_FOUND", f"task {task_id} does not exist")

    all_tasks = _load_all(root)
    task = all_tasks[task_id]

    if task.status != TaskStatus.PENDING:
        raise TaskClaimError(
            "TASK_NOT_PENDING",
            f"task {task_id} is {task.status.value}; cannot claim",
            current_owner=task.owner,
            current_status=task.status.value,
        )

    waiting = _waiting_for(task, all_tasks)
    if waiting:
        raise TaskClaimError(
            "DEPS_NOT_READY",
            f"task {task_id} waiting on {waiting}",
            waiting_for=waiting,
        )

    task = task.model_copy(
        update={
            "owner": me,
            "status": TaskStatus.CLAIMED,
            "claimed_at": datetime.now(timezone.utc),
        }
    )
    write_model(task_path, task)

    changelog_path = log_claim(root, me, task_id, task.title)
    repo.add([task_path, changelog_path])

    env = EventEnvelope(type=EventType.TASK_CLAIMED, actor=me, task_id=task_id)
    sha = repo.commit(env.dump(f"{me} claimed {task_id}"))

    pushed = False
    if sha:
        try:
            repo.push(branch="main")
            pushed = True
        except OfflineError:
            pushed = False

    return {"task_id": task_id, "sha": sha, "pushed": pushed}


# Re-export helper for tests / callers that want to read but not write.
def read_task(local_path: str | Path, task_id: str) -> TaskContract:
    return read_model(_paths.task_json(Path(local_path), task_id), TaskContract)
