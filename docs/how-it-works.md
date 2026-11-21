# 🧠 How the 5-Layer System Works

**English** | [فارسی](fa/how-it-works.md) · [← Back to README](../README.md)

Obsi Founder Compass turns Antigravity into a structured founder cockpit backed 100% by local Markdown and **Native Obsidian Bases** (`.base` views and inline project boards — zero third-party community plugins).

Source schema: [`skills/second-brain/SKILL.md`](../skills/second-brain/SKILL.md) · Decision rules: [`decision_frameworks.md`](../skills/second-brain/references/decision_frameworks.md).

---

## 1. The 5-Layer Hub-and-Spoke Architecture

| Layer | Command | Responsibility | Key Guardrail |
| :---: | :--- | :--- | :--- |
| **0** | `/obsi-setup` | Scaffolds Vault, calendars (`en` Mon–Sun or `fa` Sat–Fri), pillars, projects, and `brain-os.json` | `--dry-run` preview + skips existing notes |
| **1** | `/obsi-consult` | Market audit, buyers, pricing, trust, and **Macro Focus Bundles** | **Vision Mirror Gate** + **No-Code Firewall** + **No Capacity Policing** |
| **2** | `/obsi-priority` | Converts approved Macro Bundles into 14-day **Cohorts** & atomic tasks | Strictly **advisory** workload pacing (`Scale / Pivot / Kill`) |
| **3** | `/obsi` | Smart clickable palette (`resolve_obsi_hub.py`), quick capture, `/obsi next`, `/obsi done` | Auto-unlocks dependent `Locked` cards on completion |
| **4** | `/obsi-inspect` | Audits recent chat turns for unverified claims + 1s Vault health check | Reads exact delta (`transcript.jsonl`) via `extract_session_steps.py` |

---

## 2. Native Obsidian Bases Vault (SSOT)

Every Vault scaffolded by [`scaffold_brain.py`](../skills/obsi-setup/scripts/scaffold_brain.py) enforces a Single Source of Truth:

- **`00-Home.md`** — Live cockpit embedding `Today.base`, `Weekly.base`, and `Cohorts.base` (never manually pasted task lists).
- **`Today.base` · `Weekly.base` · `Tasks.base`** — Dynamic `.base` views filtering `status == "Sprint" || status == "Doing"` without hardcoded sprint labels, always including `null` in Kanban `groupOrder`.
- **`00-Focus/Cohorts/`** — Time-boxed 14-day experiments with `quota_target`, `time_window`, `Leading`/`Lagging` metrics, and `Scale / Pivot / Kill` decision gates.
- **`00-Focus/Scorecards/`** — Stateful strategic memory per project (`last_full_audit`, `active_deep_dive`, Macro Focus Bundles) enabling zero-search **Route B** resume across chats.
- **`01-Projects/`** — Isolated project hubs with `type: project`, `pillar:`, `workspace:`, and an embedded inline `` ```base `` board.

---

## 3. Strategy Guardrails in `/obsi-consult`

1. **Vision Mirror Gate (Hard Stop):** Before launching deep research, the consultant asks at most 4 quick questions, mirrors your vision back in 4 plain lines, and waits for explicit approval.
2. **Cache-First Market Playbooks:** [`consult_audit.py`](../skills/obsi-consult/scripts/consult_audit.py) checks [`playbooks/index.json`](../skills/obsi-consult/playbooks/index.json) (`90-day` TTL) before issuing web searches, preventing duplicate research runs.
3. **No-Code Firewall:** Enforce-checked with `BANNED_TECH_RE` inside `consult_audit.py` — built technology is summarized in one line (*"Product infrastructure is online"*) so strategy conversations stay purely commercial.
4. **Sequential Task Unlocking:** Tasks in `02-Tasks/<Pillar>/<Project>/` can declare `depends_on: "[[Blocker-Task]]"` and `status: Locked`. Completing the blocker via `/obsi done` automatically promotes dependent cards to `Sprint`.
