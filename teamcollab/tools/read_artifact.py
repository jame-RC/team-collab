"""``read_artifact``: local-only read of a member's submitted artifact.

No git ops — just resolves ``artifacts/<member>/<task_id>/`` and returns the
parsed :class:`Artifact` plus the raw markdown body. Callers (reviewer
subagent, integrator subagent, ad-hoc inspection) get a stable shape:

    {"artifact": Artifact, "content": str, "content_path": str}

Raises :class:`ArtifactNotFoundError` if either ``meta.json`` or
``content.md`` is missing — typically means the member never submitted, or
submitted under a different name.
"""
from __future__ import annotations

from pathlib import Path

from teamcollab.contracts import Artifact
from teamcollab.tools import _paths
from teamcollab.tools._io import read_model


class ArtifactNotFoundError(FileNotFoundError):
    def __init__(self, code: str, message: str, **payload):
        super().__init__(message)
        self.code = code
        self.payload = payload


def read_artifact(
    *,
    local_path: str | Path,
    member: str,
    task_id: str,
) -> dict:
    root = Path(local_path).resolve()
    art_dir = _paths.artifact_dir(root, member, task_id)

    meta_path = art_dir / "meta.json"
    content_path = art_dir / "content.md"

    if not meta_path.exists():
        raise ArtifactNotFoundError(
            "ARTIFACT_NOT_FOUND",
            f"no artifact for member={member} task={task_id}",
            member=member,
            task_id=task_id,
        )
    if not content_path.exists():
        raise ArtifactNotFoundError(
            "CONTENT_MISSING",
            f"meta exists but content.md missing for {member}/{task_id}",
            member=member,
            task_id=task_id,
        )

    artifact = read_model(meta_path, Artifact)
    content = content_path.read_text(encoding="utf-8")

    return {
        "artifact": artifact.model_dump(mode="json"),
        "content": content,
        "content_path": content_path.relative_to(root).as_posix(),
    }
