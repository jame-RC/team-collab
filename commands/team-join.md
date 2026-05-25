---
description: Join an existing TeamCollab project as a member — clone the repo locally and append yourself to members.json.
argument-hint: <remote_url> <local_path> <my_name> [capabilities_csv]
---

You are about to run `/team-join` as a **member** (not the leader). Activate the `team-member` skill.

Steps:
1. Ask for any missing arguments: `remote_url` (required), `local_path` (where to clone), `my_name`, optional `capabilities` (a list of strings declaring what you can do — e.g. `["python", "literature-review", "data-viz"]`).
2. Call `team_join`. The tool clones the repo if not present (or pulls if it is), adds you to `members.json`, and pushes.
3. If the response says `joined: false`, you were already in the project — that's fine, it's idempotent. Show the current member list so the user can confirm.
4. After success, run `task_list(filter="available", me=<my_name>)` so the user immediately sees what they can pick up.
