---
name: obsi
kind: workflow
uses:
  - second-brain
description: "[Workflow] 5-Layer Obsidian Brain Hub & Layer 3 Daily Execution (`/obsi`, `obsi`): smart 5-layer command palette via `ask_question`, rapid capture, weekly scheduling, next unlocked task, and `/obsi done` cascading unlock. Silent in normal chat."
---

# `obsi` — 5-Layer Hub & Layer 3 Execution

Trigger on **`obsi`**, **`/obsi`**, or quick capture/tactical requests. Read `~/.gemini/config/brain-os.json` to locate the user's Vault, follow `second-brain` schemas, and confirm in 1 line before mutating any Vault file.

## Thin Hub Entry Gate (`resolve_obsi_hub.py`)
On bare **`/obsi`** (no subcommand), run [resolve_obsi_hub.py](../second-brain/scripts/resolve_obsi_hub.py):
`python "<second-brain-dir>/scripts/resolve_obsi_hub.py" --cwd "<workspace>" --json`
Display `summary_2lines` and (if non-empty) `project_tasks_card` (top 5 one-line active tasks for the current project + locked/backlog counts), then call **`ask_question`** with `recommended_options`:
- **`needs_setup`** -> launch Layer 0 (`obsi-setup`).
- **`ready`** -> let the user pick any of the 5 layers in 1 click:
  - **Layer 0 (`obsi-setup`)** · **Layer 1 (`obsi-consult`)** · **Layer 2 (`obsi-priority`)** · **Layer 3 (`obsi` daily)** · **Layer 4 (`obsi-inspect`)**.

## Layer 3 Direct Shortcuts (Daily Execution)
| Shortcut | Action | Destination / Ref |
| :--- | :--- | :--- |
| **`obsi <text>`** *(capture)* | Detect layer (Cohort, Project, Rock, Task, Idea), draft YAML, confirm in 1 line, write cleanly. | `second-brain` |
| **`/obsi next`** | Surface the single highest-priority unlocked active task ready now. | `Today.base` / `Tasks.base` |
| **`/obsi tactical`** | Plan weekly day slots with concrete half-line `action:` (`Mon–Sun` or `Sat–Fri`). | `Weekly.base` |
| **`/obsi log [task]`** | Log partial progress (`status: Doing`, refresh `action:`, append dated progress note without closing prematurely). | `02-Tasks/` |
| **`/obsi done [task]`** | Set `status: Done`, `today: false`, `completed: YYYY-MM-DD`; unlock matched `depends_on` tasks (`Locked` -> `Sprint`). | `02-Tasks/` |

## Execution Rule
1. Propose target layer, 1-line summary, and key YAML fields; wait for user confirmation before writing.
2. Enforce SSOT (never duplicate `.base` views or Cohort logs) and reply with clickable `file:///` links.
