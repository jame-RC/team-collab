---
description: Submit a task artifact as the claiming member. Writes content + meta under artifacts/<you>/<task_id>/ and pushes.
argument-hint: <local_path> <task_id> <my_name> [refs_csv]
---

You are about to run `/team-submit` as a **member**. Activate the `team-member` skill.

Steps:
1. Read the task's `output_schema` from `tasks/<task_id>.json` so you know whether content should be markdown or JSON. If JSON, validate the user's content parses before submitting.
2. Confirm the user has actually written the content. If they invoke `/team-submit` with no content prepared, ask them to paste it (or point at a local file path you can read).
3. Call `task_submit` with `local_path`, `task_id`, `actor=<my_name>`, the full `content` string, and optional `refs` (list of pointer paths to upstream artifacts the user cited).
4. Handle structured errors:
   - `NOT_OWNER`: the user didn't claim this task (or someone else did). Tell them to `/team-claim` first or pick a different task.
   - `SCHEMA_VIOLATION`: surface the validator's message and let the user fix and resubmit — no need to re-claim.
   - `TASK_NOT_CLAIMABLE_STATE`: the task is already `submitted` or `approved`. If a review came back as `needs_revision`, status will be back to `in_progress` and this won't trigger.
5. On success, the task status is now `submitted` and the leader (or the GitHub Action fallback) will trigger review. Tell the user where their artifact landed: `artifacts/<my_name>/<task_id>/content.md`.
