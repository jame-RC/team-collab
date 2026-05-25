"""``task_review``: any authorized team member posts a verdict for a submitted task.

The reviewer can be the leader, a designated peer reviewer, or any member
with review privileges. There is no hard role constraint — the caller decides
who reviews each task (typically set by the task's review workflow or by the
coordinator skill).

Writes ``reviews/<task_id>-review.json`` and flips the task status:

* ``approved``        → ``TaskStatus.APPROVED``  (downstream tasks unblock)
* ``needs_revision``  → ``TaskStatus.NEEDS_REVISION``  (owner can resubmit)
* ``rejected``        → ``TaskStatus.REJECTED``

Commit carries ``EventEnvelope(type=review_posted)``.
"""
from __future__ import annotations

from pathlib import Path

from teamcollab.contracts import (
    EventEnvelope,
    EventType,
    ReviewComment,
    ReviewResult,
    TaskContract,
    TaskStatus,
    Verdict,
)
from teamcollab.git_ops import GitRepo, OfflineError
from teamcollab.tools import _paths
from teamcollab.tools._changelog import log_review
from teamcollab.tools._io import read_model, write_model


_VERDICT_TO_STATUS = {
    Verdict.APPROVED: TaskStatus.APPROVED,
    Verdict.NEEDS_REVISION: TaskStatus.NEEDS_REVISION,
    Verdict.REJECTED: TaskStatus.REJECTED,
}


class TaskReviewError(RuntimeError):
    def __init__(self, code: str, message: str, **payload):
        super().__init__(message)
        self.code = code
        self.payload = payload


def task_review(
    *,
    local_path: str | Path,
    task_id: str,
    reviewer: str,
    verdict: Verdict,
    score: int,
    comments: list[dict] | list[ReviewComment] | None = None,
) -> dict:
    root = Path(local_path).resolve()
    repo = GitRepo(root)

    try:
        repo.pull(branch="main")
    except OfflineError:
        pass

    task_path = _paths.task_json(root, task_id)
    if not task_path.exists():
        raise TaskReviewError("TASK_NOT_FOUND", f"task {task_id} does not exist")

    task = read_model(task_path, TaskContract)

    parsed_comments: list[ReviewComment] = []
    for c in comments or []:
        if isinstance(c, ReviewComment):
            parsed_comments.append(c)
        else:
            parsed_comments.append(ReviewComment.model_validate(c))

    review = ReviewResult(
        task_id=task_id,
        verdict=verdict,
        score=score,
        comments=parsed_comments,
        reviewer=reviewer,
    )
    review_path = _paths.review_json(root, task_id)
    write_model(review_path, review)

    task = task.model_copy(update={"status": _VERDICT_TO_STATUS[verdict]})
    write_model(task_path, task)

    comment_summary = parsed_comments[0].message if parsed_comments else None
    changelog_path = log_review(
        root, reviewer, task_id, task.title,
        verdict=verdict.value, score=score,
        comment_summary=comment_summary,
    )
    repo.add([review_path, task_path, changelog_path])
    env = EventEnvelope(type=EventType.REVIEW_POSTED, actor=reviewer, task_id=task_id)
    sha = repo.commit(env.dump(f"{reviewer} reviewed {task_id}: {verdict.value}"))

    pushed = False
    if sha:
        try:
            repo.push(branch="main")
            pushed = True
        except OfflineError:
            pushed = False

    return {
        "task_id": task_id,
        "verdict": verdict.value,
        "new_status": task.status.value,
        "sha": sha,
        "pushed": pushed,
    }
