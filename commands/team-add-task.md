---
description: Add a single new task mid-project (the leader realized something was missing or needs to split an existing task). Same DAG validation as /team-tasks, one item.
argument-hint: <local_path> "<title>" <owner> [deps_csv]
---

You are about to run `/team-add-task` as the team **leader**. Activate the `team-coordinator` skill.

Steps:
1. Confirm the new task with the leader: title, brief, owner, deps. Auto-generate a fresh `task_id` continuing from the highest existing one.
2. Validate locally before calling the tool: owner exists in `members.json`, every dep id exists in `tasks/`, the new id doesn't collide.
3. Call `task_add` with the constructed `TaskContract`. The MCP tool re-validates the DAG — adding a cycle is rejected with a structured error.
4. On success, show the task id and (if applicable) which downstream task is now waiting on the new one.

If the leader is splitting an existing oversized task, do not delete the original here — that's a separate decision. Just add the new piece and let the leader manage status by hand if needed.
