---
description: Interactively dictate the task list for a TeamCollab project. The leader speaks; the skill structures each item into a TaskContract, validates the DAG, and writes them in one commit. Run after /team-init.
argument-hint: <local_path> [actor_name]
---

You are about to run `/team-tasks` as the team **leader**. Activate the `team-coordinator` skill.

This is an **interactive dictation flow**. The leader will paste or type a list of tasks in natural language (e.g. "First Bob does the literature review. Then Carol writes the experiment section based on Bob's output. I'll handle the introduction in parallel."). Your job:

1. Read `members.json` at `<local_path>` to know who's eligible to be `owner`.
2. Read `tasks/` to see what task ids already exist (so new ones don't collide).
3. For each item the leader describes, draft a `TaskContract`:
   - `task_id`: auto-generate as `task-NNN` continuing from the highest existing id
   - `title`: short imperative phrase
   - `brief`: one or two sentences of what success looks like
   - `owner`: must match a name in members.json
   - `deps`: list of task_ids this depends on (resolve from "after X" / "based on Y" / "once Z is done" phrasing)
   - `output_schema`: pick a sensible default — `markdown` for prose, `json` for structured data
4. Show the proposed list as a compact table: `task_id | owner | deps | title`. Ask the leader: "Confirm and write? (yes / edit task-NNN / cancel)".
5. On confirmation, call `task_create_batch` with the full list. The MCP tool re-validates the DAG (no cycles, no dangling deps, no duplicate ids, all owners known). If it returns an error, surface the offending task ids and let the leader fix that one item without redoing the rest.
6. Surface soft warnings (do not block):
   - one task has > 3 downstream tasks all directly depending on it (single-bottleneck)
   - a task has no `owner` in members.json (orphan — should have been caught, but double-check)
   - one owner has > N tasks where N is the average × 2 (overloaded)

After success, show the new task ids and remind the leader that members can now `/team-claim` available ones.
