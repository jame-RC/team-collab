"""Append-only operation log written to CHANGELOG.md at project root.

Each significant action (claim, submit, review) gets a timestamped entry
so the team can see a human-readable history of all contributions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _ensure_header(changelog: Path) -> None:
    if not changelog.exists():
        changelog.write_text("# 项目操作日志\n\n", encoding="utf-8")


def append_changelog(root: Path, entry: str) -> Path:
    """Append a markdown entry to CHANGELOG.md and return its path."""
    changelog = root / "CHANGELOG.md"
    _ensure_header(changelog)
    with changelog.open("a", encoding="utf-8") as f:
        f.write(entry + "\n\n")
    return changelog


def log_claim(root: Path, actor: str, task_id: str, task_title: str) -> Path:
    entry = (
        f"## {_now_str()} — {actor} 领取了 {task_id}\n"
        f"**任务**: {task_title}"
    )
    return append_changelog(root, entry)


def log_submit(
    root: Path,
    actor: str,
    task_id: str,
    task_title: str,
    content_summary: str | None = None,
    extra_files: list[str] | None = None,
) -> Path:
    lines = [
        f"## {_now_str()} — {actor} 提交了 {task_id}",
        f"**任务**: {task_title}",
    ]
    if extra_files:
        files_str = ", ".join(extra_files)
        lines.append(f"**附加文件**: {files_str}")
    if content_summary:
        lines.append(f"**摘要**: {content_summary}")
    return append_changelog(root, "\n".join(lines))


def log_review(
    root: Path,
    reviewer: str,
    task_id: str,
    task_title: str,
    verdict: str,
    score: int,
    comment_summary: str | None = None,
) -> Path:
    verdict_cn = {"approved": "通过", "needs_revision": "需修改", "rejected": "拒绝"}
    lines = [
        f"## {_now_str()} — {reviewer} 评审了 {task_id}",
        f"**任务**: {task_title}",
        f"**结果**: {verdict_cn.get(verdict, verdict)} ({score}/100)",
    ]
    if comment_summary:
        lines.append(f"**评语**: {comment_summary}")
    return append_changelog(root, "\n".join(lines))
