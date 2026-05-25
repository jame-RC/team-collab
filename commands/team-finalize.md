---
description: Promote the integrator's draft deliverable to the final version, or run integration locally if the draft doesn't exist yet.
argument-hint: <local_path> <leader_name>
---

You are about to run `/team-finalize` as the team **leader**. Activate the `team-coordinator` skill.

Steps:
1. Call `task_list(filter="all")` and verify every task is `approved`. If not, list the outstanding ones and stop — finalization is premature.
2. Check the repo for `final/deliverable.md` and `final/deliverable.draft.md`:
   - **Both missing**: the GitHub Action hasn't run (no API key, or leader's been online the whole time). Spawn the `integrator` subagent with all approved artifacts + glossary + citation_style → write directly to `final/deliverable.md` via `task_submit`-style commit (use the dedicated `final_write` path; the coordinator skill knows how). Skip the draft step.
   - **Draft exists, no final**: the Action wrote a draft while the leader was offline. Show a diff summary (sections / headings only — full diff is too noisy). Ask the leader to read `final/deliverable.draft.md` and either (a) accept as-is, (b) edit inline, or (c) re-run the integrator subagent locally for a fresh pass.
   - **Final already exists**: tell the leader it's already done; ask if they want to re-integrate (rare — usually means a late revision came in).
3. On accept-as-is, do `git mv final/deliverable.draft.md final/deliverable.md` + commit with `EventEnvelope: final_integrated` + push. The coordinator skill should call the appropriate MCP tool rather than running git commands directly.
4. On edit-and-promote, write the leader's edited content to `final/deliverable.md`, delete the draft, commit + push.
5. After success, surface the final commit SHA and the deliverable path so the leader can hand it in.
