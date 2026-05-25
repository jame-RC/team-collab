"""Layout of the blackboard repo.

Every tool reads/writes through these helpers so the on-disk layout is defined
in exactly one place. If the layout ever changes, only this module moves.
"""
from __future__ import annotations

from pathlib import Path


def project_json(root: Path) -> Path:
    return root / "project.json"


def members_json(root: Path) -> Path:
    return root / ".teamcollab" / "members.json"


def glossary_json(root: Path) -> Path:
    return root / "glossary.json"


def tasks_dir(root: Path) -> Path:
    return root / "tasks"


def task_json(root: Path, task_id: str) -> Path:
    return tasks_dir(root) / f"{task_id}.json"


def artifact_dir(root: Path, member: str, task_id: str) -> Path:
    return root / "artifacts" / member / task_id


def review_json(root: Path, task_id: str) -> Path:
    return root / "reviews" / f"{task_id}-review.json"


def teamcollab_dir(root: Path) -> Path:
    return root / ".teamcollab"
