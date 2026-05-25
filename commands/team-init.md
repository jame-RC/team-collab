---
description: Bootstrap a new TeamCollab project — create the local repo (and optionally a GitHub remote), write project.json / members.json / glossary.json / Actions workflow, and commit. Run this once as the team leader.
argument-hint: <local_path> "<title>" "<brief>" <leader_name> [remote_url]
---

You are about to run `/team-init` as the team **leader**. Activate the `team-coordinator` skill.

Arguments expected from the user (ask if missing):
- `local_path` — where to create the local repo on disk
- `title` — short project name
- `brief` — one-paragraph description of the assignment
- `leader` — the leader's name (this user)
- `leader_capabilities` — optional list of strings declaring what the leader can do
- `deadline` — optional ISO date
- `remote_url` — optional; if provided, the initial commit is pushed there. If omitted the project stays local-only and can be pushed later.

Call the `team_init` MCP tool with these arguments. After it succeeds:
1. Show the user the absolute path of the new repo and the SHA of the initial commit.
2. Remind them that **no tasks exist yet** — they should run `/team-tasks` next to dictate the task list.
3. If `remote_url` was provided but the push failed (offline), tell the user the commit is local and will push on the next `/team-sync`.

Do NOT auto-create tasks here. Task definition is a separate, deliberate step the leader controls via `/team-tasks`.
