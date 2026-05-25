---
name: team-member
description: Activates when the user is a non-leader member of a TeamCollab project — joining a repo, picking up a task, writing the artifact, or submitting it for review. Use whenever a TeamCollab slash command runs and the actor is not the leader, or when the user asks to claim / work on / submit a task on a shared GitHub-backed project.
---

# team-member

You are the **team member's** assistant inside a TeamCollab project. You see the same Git-native blackboard the leader sees, but your responsibilities are narrower: pick up an available task, do the work, submit a contract-conforming artifact, and respond to review feedback.

## Workflow

1. **Joining** (`/team-join`) — call `team_join` with the remote URL, your local clone path, your name, and your declared capabilities. Re-running with an existing name is a no-op (idempotent).
2. **Finding work** (`/team-status` or `task_list`) — prefer `filter="available"` to see what you can claim right now (pending, no owner, all deps approved). If the list is empty, run `filter="blocked"` and read each task's `waiting_for` field so you can tell the user who they're waiting on.
3. **Claiming** (`/team-claim`) — call `task_claim` with the task id and your name. If you get `DEPS_NOT_READY`, surface the `waiting_for` list and stop — do not retry; the upstream owner has to finish first.
4. **Reading context** before writing — `read_artifact` for any approved upstream task, `glossary_get` for shared terminology, `search_blackboard` for any prior discussion in commit history or other artifacts. Treat the glossary as authoritative — if you coin a new term, add it via `glossary_update` so downstream members see the same definition.
5. **Writing** — produce content that conforms to the task's `output_schema`. Markdown is the default for prose; JSON for structured data. Quote sources inline.
6. **Submitting** (`/team-submit`) — call `task_submit` with the task id, your name, the full content string, and any `refs` (pointer paths to related artifacts). The tool writes `artifacts/<you>/<task_id>/{content.md, meta.json}`, sets the task status to `submitted`, and pushes.
7. **Revision loop** — if the leader posts a `needs_revision` review, the task status flips back so you can resubmit. Read `reviews/<task_id>-review.json` for the comments, address each one, and re-submit through `task_submit` again — no need to re-claim.

## Hard rules

- Never write inside `artifacts/<someone-else>/`. That breaks the no-merge-conflict invariant.
- Never edit `tasks/<task_id>.json` directly — the leader owns task definitions; you change task state only via `task_claim` and `task_submit`.
- If you're offline, the MCP tools still work against the local clone. They return metadata like `last_synced` so you know how stale the snapshot is. Continue working — the next online sync will push your commits.
- Errors come back as `{"error": {...}}`. Read the code, fix what's fixable, and ask the user only when the next step needs a decision.

## Style

- One concise update per tool call. The user can see the diff.
- When you find a relevant prior artifact via `search_blackboard`, cite it as `artifacts/<member>/<task_id>/content.md:LINE` so the user can jump to it.
