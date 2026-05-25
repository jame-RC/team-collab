---
description: Show overall project progress — task list with status, owner, deps, and an ASCII DAG of the dependency graph.
argument-hint: <local_path> [filter]
---

You are about to run `/team-status`. Activate `team-coordinator` if the user is the leader, otherwise `team-member`.

Steps:
1. Call `task_list` with `local_path`, `filter=<filter or "all">`, and `tree=true` so the response includes the ASCII DAG.
2. Render two views:
   - A compact table: `task_id | status | owner | deps | title`. Use single-letter status codes if helpful (`P`=pending, `I`=in_progress, `S`=submitted, `A`=approved, `R`=needs_revision).
   - The ASCII tree from `tree_ascii` field, rendered verbatim in a code block.
3. If the response includes `last_synced` older than ~10 minutes, suggest `/team-sync` so the user is looking at fresh state.
4. If the user is a member and `filter="available"` returned an empty list, also surface `blocked` tasks with their `waiting_for` field so the user knows whose upstream work is gating them.
5. Soft warnings to surface (do not block):
   - any task in `submitted` for > 24h with no review (the leader / Action fallback may have stalled)
   - any owner with > 3 `in_progress` tasks (likely overloaded)
