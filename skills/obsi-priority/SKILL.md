---
name: obsi-priority
kind: workflow
uses:
  - second-brain
description: "[Workflow] Layer 2 Advisory Prioritization & Cohort Design (`/obsi-priority`): turns Macro Focus Bundles from Scorecards into selectable time-boxed Cohorts (`Scale/Pivot/Kill`) and atomic tasks with non-prescriptive workload options. Silent in normal chat."
---

# `obsi-priority` — Layer 2 Advisory Prioritization & Cohort Designer

Active **ONLY** on **`/obsi-priority`** (or right after locking project Scorecards in `/obsi-consult`). Dormant in normal engineering chat. **NEVER** mutate Vault files before explicit user approval.

## Strict Advisory Rule (Founder Always Decides)
- Workload checks are **strictly advisory** (`governance_and_audit.md` §4 & `decision_frameworks.md` §1, §2).
- Present combined capacity context neutrally with optional sequencing choices; **NEVER** force-park or kill any project.

## Workflow
1. **Load Context:** Locate `<Vault>` via `~/.gemini/config/brain-os.json` and read `00-Focus/Scorecards/*.md` (especially `Macro Focus Bundles`), active `00-Focus/Monthly-Plans/*.md`, `00-Focus/Cohorts/*.md`, and `02-Tasks/`.
2. **Propose Cohort Options (Proposal-First):**
   - For the selected project's Macro Bundles, draft 2–3 concrete **Time-Boxed Cohort** options with `quota_target`, `time_window`, `checkpoints`, `Leading`/`Lagging` metrics, and clear `Scale / Pivot / Kill` gates (`Cohort Template.md`).
   - Show combined workload neutrally with 1–2 pacing options so the founder refines quotas and picks freely.
3. **Save After Approval:**
   - Write approved Cohort(s) into `00-Focus/Cohorts/Cohort - <Title>.md`, atomic tasks into `02-Tasks/<Pillar>/<Project>/` (`depends_on:` where sequential unlock applies), sync `Monthly-Plans/` + `Scorecards/<Project>.md`, and report clickable `file:///` links.
