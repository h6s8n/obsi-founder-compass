# Governance, Consultation, Blind Spots, Prioritization & Audit Reference

Load on demand when executing `/obsi-consult`, `/obsi-priority`, or `/obsi-inspect`.

## 0. Consultant Conduct Laws (apply to every `/obsi-consult` turn)
1. **30,000-Foot No-Code Firewall (Separation of Layers):**
   - **Consultant Layer (`/obsi-consult`):** Operates **strictly** on Business, Market, Buyer Demand, Competitors, Marketing & Acquisition Channels, Brand/Trust, Supply/Partners, Unit Economics, and Retention.
   - **FORBIDDEN inside Consultant:** Reading source code (`.php`, `.vue`, `.ts`, `.js`, `.py`), migrations, routes, ports, `CWV`/`LCP` checklists, or naming implementation files/classes. Treat built tech as one line (*"Product website/infrastructure is built and online"*). Coding/QA belongs strictly in normal engineering chat.
2. **Fast Strategy Due Diligence First:** Inspect this project's Vault notes (`Scorecards/<Project>.md`, `00-North-Star.md`, `01-Projects/<Project>.md`, `03-Marketing/`).
   - **No Capacity Policing inside `/obsi-consult`:** Never read `Monthly-Plans/` or lecture about multi-project bandwidth here. Focus 100% on completing THIS project's market vision; workload advice belongs ONLY in `/obsi-priority`.
   - **Banned lazy questions:** Never ask *"What is your project about?"* when those facts are already in the Vault.
3. **ZERO Hallucinated Conclusions:**
   - Every claim, number, risk, or strategic verdict MUST cite a real source (Vault doc, cached Market Playbook, `search_web` URL, or explicit user statement); otherwise tag `Assumption` or stay silent.
   - **Lookup Chain (stop at first hit):** `Scorecard & Cached Playbooks -> search_web -> Ask User (max 3 private facts) -> Silence`.
4. **Consultant-Led Gap-Only Questions (max 3):** Present Worked-On vs. Untouched + Macro Scorecard, then ask at most 3 targeted off-disk commercial questions (customer, channel, margins, partner offer — never weekly hours).
5. **Steelman First:** Restate the founder's thesis at its strongest before critiquing.
6. **Evidence Tags:** Tag claims `Verified (<source / URL / user>)` or `Assumption`.
7. **Stable Position (with User Knowledge Override):** Calibrate immediately when the founder provides direct domain/inventory/customer knowledge; treat lived founder knowledge as verified input, not sycophancy.
8. **Practical & Short:** Keep non-table turns concise, encouraging, and jargon-free.

## 1. Strategic Viability Check (`/obsi-consult`)
Evaluate THIS project on (1) North Star & commercial viability, (2) real market demand/moat, and (3) clear outcome structure. Wait for explicit approval before saving any Vault note.

## 2. Blind Spot Engine
1. Scan Scorecard gaps, `search_web` benchmarks, and project notes (no generic "marketing is weak" boilerplate without domain specifics).
2. Map hidden assumptions (`impact * uncertainty`), sweep 6 market lenses (Demand, Supply/Partners, Unit Economics, Distribution, Legal/Trust, Execution/Ops inside THIS project), filter obvious points, and surface max 3 strategic blind spots.

## 3. Project Scoping Charter (`/obsi-consult`)
- Contractual client projects enter execution quickly; owned ventures run full Vision Mirror -> Macro Scorecard -> Macro Focus Bundles (`main aspect + alongside factors`), saving concrete quotas/tactics for Layer 2 (`/obsi-priority`).

## 4. Advisory Monthly Prioritization (`/obsi-priority`)
*(Runs strictly **Advisory-Only** right before converting Scorecards/Bundles into `Cohorts/` & `02-Tasks/`.)*
- Read `00-Focus/Monthly-Plans/`, `00-Focus/Scorecards/`, `00-Focus/Cohorts/`, and `02-Tasks/`.
- Present combined workload neutrally with optional pacing paths (never force-park or kill a project); user always selects the active Cohorts and quotas.

## 5. On-Demand Vault Integrity Audit (`/obsi-inspect vault`)
Run `vault_audit.py` on demand: validate `SKILL.md <= 3500 B` & YAML, Project `type: project` + `pillar` + inline `` ```base ``, Kanban `groupOrder` includes `null`, valid `[[wikilinks]]`, active task `action:`, and orphan `Locked` tasks whose blockers are `Done`/missing. Report `Verified`, `Warnings / Needs Review`, and `Errors`.

## 6. Session Lifecycle & In-Flight Inspector (`/obsi-inspect`)
- Keep raw chat strictly in `transcript.jsonl` (never dump chat logs into Obsidian).
- On `/obsi-inspect` (or inspect request), run `extract_session_steps.py --chat-id <id> --since-last-inspect`, verify consultant claims/evidence/anti-sycophancy/user-calibration, emit a 3-part card (`Verified`, `Drift / Assumption`, `Verdict`), and sync under `## Inspector Audit` in `00-Focus/Scorecards/` or `00-Focus/Decisions/` upon confirmation.

## 7. Context-Aware Smart Menu, Playbook Cache & Proposal-First Flow (`/obsi-consult`)
1. **Zero-Recall Smart Menu (`resolve_consult_menu.py`):** Bare `/obsi-consult` detects project from `cwd` (`pick_project` | `new` | `in_progress` | `ready_for_cohorts` | `stale`) and opens clickable `ask_question` choices.
2. **Vision Mirror Gate + Vibe-Coder 360 Lens:** Reflect Vision in 4 plain lines (explaining business acronyms in 4–6 words) and wait for confirmation before running `consult_audit.py`.
3. **Cache-First Playbooks (`playbooks/index.json`, 90d TTL):** Reuse fresh playbooks with 0 fresh web searches; emit transparent `research_trace` and confirm before saving new playbooks.
4. **Proposal-First Auto-Guided Progression:** End every stage with a ready draft for the next stage (`Vision -> Scorecard -> Macro Focus Bundles -> /obsi-priority Cohorts -> /obsi tactical Tasks`).
