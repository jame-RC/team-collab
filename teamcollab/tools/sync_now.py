"""``sync_now``: explicit ``git pull --rebase && git push``.

Useful when the user wants to force a sync without performing any other
mutation (e.g. ``/team-sync``). Both directions are offline-tolerated: we
report what succeeded so the caller can show "queued for next sync" UI.
"""
from __future__ import annotations

from pathlib import Path

from teamcollab.git_ops import GitRepo, OfflineError


def sync_now(
    *,
    local_path: str | Path,
    branch: str = "main",
) -> dict:
    root = Path(local_path).resolve()
    repo = GitRepo(root)

    pulled = False
    pushed = False
    pull_error: str | None = None
    push_error: str | None = None

    try:
        repo.pull(branch=branch)
        pulled = True
    except OfflineError as e:
        pull_error = str(e) or "offline"

    try:
        repo.push(branch=branch)
        pushed = True
    except OfflineError as e:
        push_error = str(e) or "offline"

    return {
        "pulled": pulled,
        "pushed": pushed,
        "head_sha": repo.head_sha(),
        "pull_error": pull_error,
        "push_error": push_error,
    }
