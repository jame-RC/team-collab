"""``team_join``: clone a team-collab repo and register the new member.

Steps:

1. ``git clone <remote_url> <local_path>``.
2. Append a :class:`MemberInfo` to ``.teamcollab/members.json``.
3. Also append to ``project.json``'s ``members`` list (so a fresh clone has
   the full roster without consulting members.json separately).
4. Commit with :class:`EventEnvelope` of type ``member_joined`` and push.

Idempotent: re-joining with the same name is a no-op (no duplicate entry,
no commit, returns ``joined=False``). Push failure on the join commit is
swallowed — the local state is correct and the next sync will publish it.
"""
from __future__ import annotations

from pathlib import Path

from teamcollab.contracts import EventEnvelope, EventType, MemberInfo, ProjectMeta, Role
from teamcollab.git_ops import GitRepo, OfflineError
from teamcollab.tools import _paths
from teamcollab.tools._io import read_json, read_model, write_json, write_model


def team_join(
    *,
    remote_url: str,
    local_path: str | Path,
    name: str,
    role: Role = Role.MEMBER,
    capabilities: list[str] | None = None,
) -> dict:
    dest = Path(local_path).resolve()
    if (dest / ".git").exists():
        repo = GitRepo(dest)
    else:
        repo = GitRepo.clone(remote_url, dest)

    repo.pull(branch="main")

    members_path = _paths.members_json(dest)
    raw = read_json(members_path) if members_path.exists() else []
    members_list = list(raw) if isinstance(raw, list) else []

    if any(m.get("name") == name for m in members_list):
        return {
            "local_path": str(dest),
            "joined": False,
            "sha": None,
            "pushed": True,
        }

    new_member = MemberInfo(name=name, role=role, capabilities=capabilities or [])
    members_list.append(new_member.model_dump(mode="json"))
    write_json(members_path, members_list)

    project_path = _paths.project_json(dest)
    project = read_model(project_path, ProjectMeta)
    if not any(m.name == name for m in project.members):
        project.members.append(new_member)
        write_model(project_path, project)

    repo.add([members_path, project_path])
    env = EventEnvelope(type=EventType.MEMBER_JOINED, actor=name)
    sha = repo.commit(env.dump(f"{name} joined as {role.value}"))

    pushed = False
    if sha:
        try:
            repo.push(branch="main")
            pushed = True
        except OfflineError:
            pushed = False

    return {
        "local_path": str(dest),
        "joined": True,
        "sha": sha,
        "pushed": pushed,
    }
