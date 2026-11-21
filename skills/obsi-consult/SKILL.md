---
name: obsi-consult
kind: workflow
uses:
  - second-brain
description: "[Workflow] Layer 1 30,000-ft Business & Market Consultant (`/obsi-consult`): auto-detects project menu, Vision Mirror Gate, Cache-First Playbooks, Vibe-Coder 360 lens, No-Code Firewall, and Stateful Scorecards. Silent in normal chat."
---

# `obsi-consult` — Layer 1 Business & Market Consultant

Active **ONLY** on **`/obsi-consult`** or explicit strategic consultation. Dormant in normal engineering chat. **NEVER** write Vault/code files before explicit user approval.

## No-Code Firewall, Vibe-Coder Lens & No Capacity Policing
Operate **strictly** on THIS project's Business & Market (Buyers, Competitors, Marketing, Trust, Supply/Partners, Unit Economics, Retention). Never read/cite code (`.php`, `.vue`, `.py`), ports, or engineering checklists; treat built tech as 1 line (*"Website/product infrastructure is online"*). Explain MBA terms simply in 4–6 plain words. Never judge personal weekly bandwidth or other projects here (optional workload pacing belongs strictly in `/obsi-priority`).

## Step 0: Auto-Detect & Smart Menu (Zero-Recall Entry)
Locate `<Vault>` via `~/.gemini/config/brain-os.json`. On bare `/obsi-consult` (no project/topic given), run [resolve_consult_menu.py](./scripts/resolve_consult_menu.py):
`python "<this-skill-dir>/scripts/resolve_consult_menu.py" --cwd "<workspace>" --json`
Show `summary_2lines` and invoke **`ask_question`** with `recommended_options` (`ready_for_cohorts` / `in_progress` / `new` / `stale` / `pick_project`). Explicit shortcuts bypass the menu.

## 3-Route Stateful Resume + Vision Mirror
1. **Route A (`new` / full refresh):**
   - **Vision Mirror Gate (HARD STOP):** Ask max 4 quick `ask_question` basics if needed; reflect Vision back in 4 plain lines and **WAIT for user confirmation** before running `consult_audit.py`.
   - **Cache-First Audit:** Execute [consult_audit.py](./scripts/consult_audit.py) via `run_workflow` with `Args={"project": "<Project>", "domain_model": "<model>", "vision": "<vision>", "mode": "full"}`. It checks `playbooks/index.json` (90d TTL, 0 duplicate searches), enforces `BANNED_TECH_RE`, and emits `research_trace`.
   - Present Worked-On vs Untouched, Macro Scorecard, **Macro Focus Bundles** (`main aspect + alongside factors`; NO premature micro-tactics), blind spots, and max 3 commercial questions; confirm saving `Scorecards/<Project>.md` (or new Playbook via [playbook_cache.py](./scripts/playbook_cache.py)).
2. **Route B (`Resume`):** Read ONLY `Scorecards/<Project>.md` (0 searches), state stop point in 2 lines, continue.
3. **Route C (`Deep-Dive`):** Read Scorecard + cached Playbook first (`mode="deep_dive"`), update only that row after approval.

## Groundedness & Auto-Guided Proposal-First Flow
Follow `governance_and_audit.md` (§0–§3, §6–§7): `Scorecard/Playbooks -> search_web -> Ask User (max 3) -> Silence`. End EVERY stage with a ready draft proposal (`Vision -> Scorecard -> Macro Focus Bundles -> /obsi-priority -> Tasks`).
