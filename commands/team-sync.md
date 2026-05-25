---
description: Pull latest changes from the remote and push any local commits. Safe to run anytime — fully offline-tolerant.
argument-hint: <local_path>
---

You are about to run `/team-sync`. Activate the `team-coordinator` skill if the user is the leader, otherwise `team-member`.

Steps:
1. Call `sync_now` with `<local_path>`. The tool runs `git pull --rebase && git push`, retrying glossary-style conflicts up to 3 times.
2. If the response includes `offline: true`, tell the user we couldn't reach the remote — their local commits are safe and will push on the next online sync. Do not treat this as a failure.
3. On success, surface `pulled_commits` and `pushed_commits` counts so the user knows what moved.
4. If the response includes `rebase_conflict: true` with a file list, stop and report the conflicting paths — the user must resolve manually before re-running.
