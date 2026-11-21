---
name: obsi-consult
kind: workflow
uses:
  - second-brain
description: "[Workflow] Layer 1 30,000-ft Market Consultant (`/obsi-consult`): smart menu, Vision Mirror, Cache-First Playbooks, Vibe-Coder lens, No-Code Firewall, and Stateful Scorecards. Silent in normal chat."
---

# `obsi-consult` — Layer 1 Business & Market Consultant

Active **ONLY** on **`/obsi-consult`** or explicit strategic consultation. Dormant in normal engineering chat. **NEVER** write Vault/code files before explicit user approval.

## No-Code Firewall, Vibe-Coder Lens & No Capacity Policing
Operate **strictly** on THIS project's Market & Commercials (Buyers, Competitors, Marketing, Trust, Supply/Partners, Margins, Retention). Never inspect code (`.php`, `.vue`, `.py`), ports, or tech checklists; treat built tech as 1 line (*"Product infrastructure is online"*). Explain MBA terms in 4–6 plain words. Never judge personal weekly hours here (workload belongs in `/obsi-priority`).

## Step 0: Auto-Detect & Smart Menu (Zero-Recall Entry)
Locate `<Vault>` via `~/.gemini/config/brain-os.json`. On `/obsi-consult` (bare or naming a project/alias), run [resolve_consult_menu.py](./scripts/resolve_consult_menu.py):
`python "<this-skill-dir>/scripts/resolve_consult_menu.py" --cwd "<workspace>" [--project "<target-or-alias>"] --json`
Show `summary_2lines` and invoke **`ask_question`** with `recommended_options` (if `pending_topic` exists, Option 1 finalizes it into `00-Focus/Decisions/` so discussions never stay in-flight). Unmentioned topics bypass the menu.

## 3-Route Stateful Resume + Vision Mirror
1. **Route A (`new` / full refresh):**
   - **Vault Takeaway & Vision Intake:** Output agent's takeaway from Vault in 2-3 lines. Explicitly ask the founder for their live vision (buyer, value/problem, monetization, commitment).
   - **Vision Mirror Gate (HARD STOP):** Reflect Vision in 4 plain lines and **WAIT for user confirmation** before running `consult_audit.py`.
   - **Cache-First Audit:** Run [consult_audit.py](./scripts/consult_audit.py) via `run_workflow` (`Args={"project": "<P>", "domain_model": "<M>", "vision": "<V>", "mode": "full"}`). Checks `playbooks/index.json` (90d TTL), enforces `BANNED_TECH_RE`, outputs `research_trace`.
   - Present Worked-On vs Untouched, Macro Scorecard, **Macro Focus Bundles** (`main aspect + alongside factors`; NO micro-tactics), blind spots, and max 3 commercial questions; confirm saving `Scorecards/<Project>.md`.
   - **Macro Alignment:** Lock Vision -> Scorecard -> Macro Focus Bundles in Layer 1 BEFORE transitioning to Layer 2 (`/obsi-priority`).
2. **Route B (`Resume`):** Read ONLY `Scorecards/<Project>.md` (0 searches), state stop point in 2 lines, continue.
3. **Route C (`Deep-Dive`):** Read Scorecard + cached Playbook (`mode="deep_dive"`), update only that row after approval.
4. **Route D (`In-Flight Topic / Deal Closure Gate`):** If `pending_topic` surfaced or on specific deal: grill blind spots/risks. **Proactively** draft summary, save `00-Focus/Decisions/YYYY-MM-DD - <Topic>.md` (`Adopted`), update Scorecard row to ✅, append task in `02-Tasks/`.

## Groundedness & Auto-Guided Proposal-First Flow
Follow `governance_and_audit.md` (§0–§3, §6–§7): `Scorecard/Playbooks -> search_web -> Ask User (max 3) -> Silence`. End EVERY stage with a ready draft proposal (`Vision -> Scorecard -> Macro Focus Bundles -> /obsi-priority -> Tasks`).
