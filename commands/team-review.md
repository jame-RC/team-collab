---
description: Review a submitted task as the leader. Spawns the reviewer subagent, then writes the structured verdict back to the repo.
argument-hint: <local_path> <task_id> <leader_name>
---

You are about to run `/team-review` as the team **leader**. Activate the `team-coordinator` skill.

Steps:
1. Call `read_artifact` for `<task_id>` to load the submitted content + meta. If the task is not in `submitted` state, stop and tell the user (e.g. it may already be approved, or never submitted).
2. Spawn the `reviewer` subagent with: the task's `TaskContract` (especially `brief` and `output_schema`), the artifact `content`, the artifact `refs`, and the current `glossary.json`. Ask it to return a `ReviewResult`: `{verdict: "approved" | "needs_revision", score: 0-100, comments: [...]}`.
3. Show the leader the verdict + comments and ask for confirmation before writing. The leader may edit comments inline or override the verdict — the reviewer subagent is advisory, not authoritative.
4. On confirmation, call `task_review` with `local_path`, `task_id`, `actor=<leader_name>`, `verdict`, `score`, `comments`. The tool writes `reviews/<task_id>-review.json`, sets task status to `approved` or `needs_revision`, and pushes.
5. If the verdict is `approved`, surface any downstream tasks now unblocked (their owners can `/team-claim` them next). If all tasks are now `approved`, remind the leader that `/team-finalize` (or the auto-spawned `integrator`) will produce the final deliverable.

If the leader wants to skip the reviewer subagent and write a verdict by hand, allow it — call `task_review` directly with their text. The subagent is a convenience, not a gate.
