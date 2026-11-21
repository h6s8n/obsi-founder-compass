---
name: second-brain
kind: knowledge
description: "[Knowledge] Canonical schema, SSOT architecture, and decision frameworks for Obsidian Native Bases Second Brain Vaults (Git-tracked, zero community plugins): North Star, Pillars, Monthly Focus, Time-Boxed Cohorts, Scorecards, Project Hubs, and Tasks."
---

# Central Second Brain (`<Vault>`)

Git-tracked cross-project Obsidian Vault using **native Obsidian Bases** (zero community plugins). Read `~/.gemini/config/brain-os.json` to locate the user's `<Vault>`, then inspect `00-Home.md`, `00-Focus/00-North-Star.md`, and active `00-Focus/Monthly-Plans/*.md`.

## Vault Map (SSOT — 8 Core `.base` Files + Inline Project Boards)
- `00-Home.md` — Live cockpit embedding `Today.base`, `Weekly.base`, `Cohorts.base` (never paste manual task tables/lists).
- `Today.base` | `Weekly.base` | `Tasks.base` — Global task views (`status == "Sprint" || status == "Doing"`, never hardcode sprint names, always include `null` in Kanban `groupOrder`).
- `00-Focus/` — `00-North-Star.md`, `Pillars/` (`Pillars.base`), `Monthly-Plans/`, `Cohorts/` (`Cohorts.base` — SSOT for experiment logs), `Feasibility/` (`Feasibility.base` + `evidence/`), `Scorecards/` (Stateful Resume), `Decisions/`.
- `00-Inbox/` — `Quick Capture.md`, `Ideas-Parking/` + `Ideas-Parking.base`.
- `01-Projects/` + `Projects.base` — Isolated project hubs (`type: project`, `pillar:`, `workspace:`, each embedding its inline `` ```base `` board).
- `02-Tasks/` — Atomic cards organized by pillar and project (`02-Tasks/<Pillar>/<Project>/`).
- `03-Marketing/` | `04-MOCs/` | `05-Resources/Templates/` (native `{{title}}`/`{{date}}` only) | `99-Archive/`.

## Canonical Schemas
**Task (`02-Tasks/**/*.md`):**
```yaml
---
type: task
pillar: Projects       # Family | Self | Content | Projects
cadence: finite        # finite | recurring
project: "[[AcmeSaaS]]"
sprint: ""             # Optional sprint label or ""
status: Backlog        # Backlog | Sprint | Doing | Locked | Done
action: "One clear half-line concrete action"
day: ""                # Weekday | Mon-Fri (Daily Floor) | ""
depends_on: ""         # Optional "[[<Blocker-Task>]]"
today: false
priority: High         # High | Medium | Low
area: Product          # Product | Backend | Frontend | DevOps | Marketing | SEO | AI | Ops
created: 2026-11-21
---
```
**Project (`01-Projects/**/*.md`):** MUST set `type: project`, `pillar:`, `workspace:`, and embed an inline `` ```base `` board.

## Core Laws & References
1. **SSOT:** Keep metrics logs strictly inside their `Cohort` note; keep `00-Home.md` 100% live-driven.
2. **Finite-First + Daily Floor:** Close finite open loops steadily while protecting recurring habits with a small floor.
3. **Deep Frameworks:** See `./references/decision_frameworks.md` and `./references/governance_and_audit.md`.
