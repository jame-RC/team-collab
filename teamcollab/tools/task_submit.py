"""``task_submit``: a member uploads a deliverable for a task they own.

Layout — every member has their own subtree, so two members touching different
tasks never collide on the same path:

    artifacts/<me>/<task_id>/content.md       (main document — always present)
    artifacts/<me>/<task_id>/meta.json        (an :class:`Artifact` instance)
    artifacts/<me>/<task_id>/src/             (code files — optional)
    artifacts/<me>/<task_id>/data/            (data files — optional)
    artifacts/<me>/<task_id>/attachments/     (other files — optional)

Updates the task itself: ``status=submitted`` and ``submitted_at=now``.
Commit carries ``EventEnvelope(type=artifact_submitted)`` so reviewers
(coordinator skill or GitHub Action) can pick it up.
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from teamcollab.contracts import (
    Artifact,
    EventEnvelope,
    EventType,
    TaskContract,
    TaskStatus,
)
from teamcollab.git_ops import GitRepo, OfflineError
from teamcollab.tools import _paths
from teamcollab.tools._changelog import log_submit
from teamcollab.tools._io import read_model, write_model


class TaskSubmitError(RuntimeError):
    def __init__(self, code: str, message: str, **payload):
        super().__init__(message)
        self.code = code
        self.payload = payload


def task_submit(
    *,
    local_path: str | Path,
    task_id: str,
    me: str,
    content: str,
    refs: list[str] | None = None,
    files: list[str] | None = None,
) -> dict:
    root = Path(local_path).resolve()
    repo = GitRepo(root)

    try:
        repo.pull(branch="main")
    except OfflineError:
        pass

    task_path = _paths.task_json(root, task_id)
    if not task_path.exists():
        raise TaskSubmitError("TASK_NOT_FOUND", f"task {task_id} does not exist")

    task = read_model(task_path, TaskContract)
    if task.owner != me:
        raise TaskSubmitError(
            "NOT_OWNER",
            f"{me} cannot submit {task_id} owned by {task.owner}",
            owner=task.owner,
        )
    if task.status not in (TaskStatus.CLAIMED, TaskStatus.NEEDS_REVISION):
        raise TaskSubmitError(
            "BAD_STATUS",
            f"task {task_id} is {task.status.value}; expected claimed or needs_revision",
            current_status=task.status.value,
        )

    art_dir = _paths.artifact_dir(root, me, task_id)
    art_dir.mkdir(parents=True, exist_ok=True)
    content_path = art_dir / "content.md"
    content_path.write_text(content, encoding="utf-8")

    tracked_paths: list[Path] = [content_path]

    if files:
        for file_str in files:
            src = Path(file_str).resolve()
            if not src.exists():
                raise TaskSubmitError(
                    "FILE_NOT_FOUND",
                    f"file not found: {file_str}",
                    path=file_str,
                )
            dest = _classify_and_copy(src, art_dir)
            tracked_paths.append(dest)

    meta_path = art_dir / "meta.json"
    rel_content = content_path.relative_to(root).as_posix()
    extra_files = [
        p.relative_to(root).as_posix()
        for p in tracked_paths
        if p != content_path
    ]
    artifact = Artifact(
        task_id=task_id,
        actor=me,
        content_path=rel_content,
        refs=refs or [],
    )
    write_model(meta_path, artifact)
    tracked_paths.append(meta_path)

    task = task.model_copy(
        update={
            "status": TaskStatus.SUBMITTED,
            "submitted_at": datetime.now(timezone.utc),
        }
    )
    write_model(task_path, task)
    tracked_paths.append(task_path)

    content_preview = content[:80] + "..." if len(content) > 80 else content
    changelog_path = log_submit(
        root, me, task_id, task.title,
        content_summary=content_preview,
        extra_files=extra_files or None,
    )
    tracked_paths.append(changelog_path)

    repo.add(tracked_paths)
    env = EventEnvelope(type=EventType.ARTIFACT_SUBMITTED, actor=me, task_id=task_id)
    sha = repo.commit(env.dump(f"{me} submitted {task_id}"))

    pushed = False
    if sha:
        try:
            repo.push(branch="main")
            pushed = True
        except OfflineError:
            pushed = False

    result: dict = {
        "task_id": task_id,
        "artifact_path": rel_content,
        "sha": sha,
        "pushed": pushed,
    }
    if extra_files:
        result["extra_files"] = extra_files
    return result


_CODE_SUFFIXES = {
    ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".go", ".rs",
    ".rb", ".php", ".sh", ".bat", ".ps1", ".sql", ".html", ".css",
    ".jsx", ".tsx", ".vue", ".svelte", ".swift", ".kt", ".scala",
}
_DATA_SUFFIXES = {
    ".csv", ".json", ".xml", ".yaml", ".yml", ".toml", ".xlsx", ".xls",
    ".sqlite", ".db", ".parquet",
}


def _classify_and_copy(src: Path, art_dir: Path) -> Path:
    """Copy a file into the appropriate subdirectory of the artifact dir."""
    suffix = src.suffix.lower()
    if suffix in _CODE_SUFFIXES:
        subdir = "src"
    elif suffix in _DATA_SUFFIXES:
        subdir = "data"
    else:
        subdir = "attachments"

    dest_dir = art_dir / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(src, dest)
    return dest
