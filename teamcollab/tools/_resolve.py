"""Auto-detect TeamCollab project root directory.

Resolution order:
1. Explicit ``local_path`` if provided (backwards compat)
2. ``TEAMCOLLAB_PROJECT_ROOT`` env var (set by MCP server at startup)
3. Walk up from CWD looking for ``.teamcollab/members.json``
"""
from __future__ import annotations

import os
from pathlib import Path

from teamcollab.tools._paths import find_project_root


class ProjectNotFoundError(Exception):
    """No TeamCollab project could be located."""


def resolve_project_root(local_path: str | None = None) -> Path:
    """Resolve the TeamCollab project root.

    Returns an absolute Path to the project root directory.
    Raises ProjectNotFoundError if no project can be found.
    """
    if local_path:
        return Path(local_path).resolve()

    env_root = os.environ.get("TEAMCOLLAB_PROJECT_ROOT")
    if env_root:
        p = Path(env_root)
        if (p / ".teamcollab" / "members.json").exists():
            return p.resolve()

    found = find_project_root(Path.cwd())
    if found:
        return found.resolve()

    raise ProjectNotFoundError(
        "No TeamCollab project found. "
        "Use team_init to create one, or pass local_path explicitly."
    )
