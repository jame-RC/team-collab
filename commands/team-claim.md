---
description: Claim an available task as a member. Validates that all upstream deps are approved before assigning ownership.
argument-hint: <local_path> <task_id> <my_name>
---

You are about to run `/team-claim` as a **member**. Activate the `team-member` skill.

Steps:
1. If `<task_id>` is missing, run `task_list(filter="available", me=<my_name>)` first and let the user pick one. Don't claim arbitrarily.
2. Call `task_claim` with `local_path`, `task_id`, and `my_name`.
3. Handle these structured errors specifically:
   - `DEPS_NOT_READY`: surface the `waiting_for` list (upstream task ids + their owners). Tell the user they cannot start yet and suggest `/team-status` to see overall progress. Do **not** retry.
   - `ALREADY_CLAIMED`: read `owner` from the error payload and tell the user who currently owns it. Suggest `/team-status` to find another available task.
   - `UNKNOWN_TASK`: the id doesn't exist — likely a typo or the leader hasn't pushed yet; suggest `/team-sync`.
4. On success, remind the user the task is now `in_progress` for them, and prompt them to read upstream artifacts via `read_artifact` before writing.
