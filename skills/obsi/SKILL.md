---
name: obsi
kind: workflow
uses:
  - second-brain
description: "[Workflow] 5-Layer Obsidian Brain Hub & Layer 3 Daily Execution (`/obsi`, `obsi`): smart command palette via `ask_question`, rapid capture, weekly scheduling, next unlocked task, and `/obsi done` cascading unlock. Silent in normal chat."
---

# `obsi` — Hub & Daily Execution

Trigger on **`obsi`**, **`/obsi`**, or quick capture/tactical requests. Locate `<Vault>` via `~/.gemini/config/brain-os.json`, follow `second-brain` schemas, and confirm in 1 line before mutating Vault notes.

## Entry Gate (`resolve_obsi_hub.py`)
On `/obsi` (bare or naming a project/alias), run [resolve_obsi_hub.py](../second-brain/scripts/resolve_obsi_hub.py):
`python "<second-brain-dir>/scripts/resolve_obsi_hub.py" --cwd "<workspace>" [--project "<name-or-alias>"] --json`
Show `summary_2lines` + `project_tasks_card`, then call `ask_question` with `recommended_options`:
- **`needs_setup`** -> auto-launch `obsi-setup`.
- **`ready`** *(single project, multi-project workspace, or any folder)* -> always present ONLY the 5 crisp 1–2 word architecture choices via `ask_question` (`Setup` stays out of daily menu):
  - **`Raw Idea` / `ایده خام`**: show `Ideas-Parking.base` (`query_base`) + ask idea -> `Ideas-Parking`, `Feasibility`, or `01-Projects`.
  - **`Consult` / `مشاوره`**: launch `obsi-consult` with `--pick-first` (list projects + free topic -> pick -> ask user to speak -> all-angle review).
  - **`Priority Plan` / `اولویت‌بندی`**: launch `obsi-priority`.
  - **`Daily Tasks` / `کارهای امروز`**: show tasks via MCP `list_tasks` / `query_base` + Next / Capture / Week / Done.
  - **`Audit` / `بازرسی`**: launch `obsi-inspect` (Chat Audit or Vault Audit).

## Native MCP Fast-Path
Use bundled `obsi` MCP tools directly (fallback: `resolve_obsi_hub.py`) — zero ad-hoc scripts/hardcoding:
- **`list_tasks` / `get_vault_overview`**: Instant cross-project/filtered tasks ranked by `Tasks.base`.
- **`list_bases` / `query_base`**: Dynamically parse and query any Vault `*.base` view.
- **`update_task`**: Confirm in 1 line first, then update fields and auto-unlock `depends_on` tasks on `Done`.

## Daily Shortcuts
| Shortcut | Action | Ref |
| :--- | :--- | :--- |
| **`obsi <text>`** | Detect layer (Cohort, Project, Task, Idea), draft YAML, confirm, write cleanly. | `second-brain` |
| **`/obsi next`** | Surface highest-priority unlocked active task ready now. | `Today.base` |
| **`/obsi tactical`** | Plan weekly day slots with half-line `action:` (`Mon–Sun` / `Sat–Fri`). | `Weekly.base` |
| **`/obsi log [task]`** | Log partial progress (`status: Doing`, refresh `action:`) without closing. | `02-Tasks/` |
| **`/obsi done [task]`** | Set `status: Done`, `today: false`, `completed`; unlock `depends_on` (`Locked`->`Sprint`). | `02-Tasks/` |

## Execution Rule
1. Propose target layer, 1-line summary, and key YAML fields; wait for user confirmation before writing.
2. Enforce SSOT (no duplicate `.base`/Cohort logs) and reply with `file:///` links.
