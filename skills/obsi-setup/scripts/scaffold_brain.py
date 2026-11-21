#!/usr/bin/env python3
"""
scaffold_brain.py
Zero-dependency Obsidian Native Bases Second Brain Vault scaffolder & project adder.
Supports bilingual calendars ('en' Mon-Sun, 'fa' Sat-Fri), idempotent --dry-run / --apply,
incremental --add-project, optional --git-init, and optional --config-out.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
IGNORE_WORKSPACE_DIRS = {
    ".git",
    ".github",
    ".vscode",
    ".idea",
    ".agents",
    ".agent-sessions",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    "target",
    "out",
    ".next",
    ".nuxt",
    "coverage",
    "tmp",
    "temp",
    "scratch",
    "logs",
    "cache",
    ".cache",
    "vendor",
    "bin",
    "obj",
}


def slugify_project(name: str) -> str:
    clean = re.sub(r"[\\/:*?\"<>|]+", "-", name.strip())
    return clean or "Project"


def _norm_path(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def _parse_frontmatter(txt: str) -> dict:
    m = FM_RE.match(txt)
    if not m:
        return {}
    try:
        data = yaml.safe_load(m.group(1))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _extract_link_stem(raw) -> str:
    txt = str(raw or "").strip()
    if not txt:
        return ""
    m = WIKILINK_RE.search(txt)
    return m.group(1).strip() if m else txt


def scan_workspace_subfolders(vault_path: str, workspace_dir: str) -> dict:
    ws_abs = os.path.abspath(workspace_dir)
    ws_norm = _norm_path(ws_abs)
    projects_dir = os.path.join(vault_path, "01-Projects")
    all_projects: list[dict] = []

    if os.path.isdir(projects_dir):
        for root, _, files in os.walk(projects_dir):
            for fn in sorted(files):
                if not fn.endswith(".md"):
                    continue
                fp = os.path.join(root, fn)
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    fm = _parse_frontmatter(f.read())
                if fm.get("type") != "project":
                    continue
                all_projects.append(
                    {
                        "name": os.path.splitext(fn)[0],
                        "workspace": str(fm.get("workspace") or "").strip(),
                        "parent": _extract_link_stem(fm.get("parent")),
                        "pillar": str(fm.get("pillar") or "").strip(),
                        "status": str(fm.get("status") or "").strip(),
                        "file": os.path.relpath(fp, vault_path).replace("\\", "/"),
                    }
                )

    matched_root_names = {
        p["name"].lower()
        for p in all_projects
        if p["workspace"] and _norm_path(p["workspace"]) == ws_norm
    }
    registered_in_workspace: list[dict] = []
    for p in all_projects:
        p_ws = p["workspace"]
        p_norm = _norm_path(p_ws) if p_ws else ""
        in_ws = bool(p_norm and (p_norm == ws_norm or p_norm.startswith(ws_norm + os.sep)))
        by_parent = bool(p["parent"] and p["parent"].lower() in matched_root_names)
        if in_ws or by_parent:
            registered_in_workspace.append(p)

    all_reg_ws = [_norm_path(p["workspace"]) for p in all_projects if p["workspace"]]
    unregistered_subfolders: list[dict] = []
    if os.path.isdir(ws_abs):
        try:
            entries = list(os.scandir(ws_abs))
        except OSError:
            entries = []
        for entry in entries:
            try:
                if not entry.is_dir():
                    continue
            except OSError:
                continue
            if entry.name.startswith(".") or entry.name.lower() in IGNORE_WORKSPACE_DIRS:
                continue
            entry_norm = _norm_path(entry.path)
            if any(rw == entry_norm or rw.startswith(entry_norm + os.sep) for rw in all_reg_ws):
                continue
            unregistered_subfolders.append(
                {
                    "name": entry.name,
                    "path": os.path.abspath(entry.path),
                    "is_git_repo": os.path.isdir(os.path.join(entry.path, ".git")),
                }
            )
    unregistered_subfolders.sort(key=lambda d: (not d["is_git_repo"], d["name"].lower()))

    return {
        "workspace": ws_abs,
        "vault": vault_path,
        "registered_in_workspace": registered_in_workspace,
        "unregistered_subfolders": unregistered_subfolders,
    }


def build_base_files(lang: str) -> dict[str, str]:
    if lang == "fa":
        days_list = [
            "شنبه",
            "یکشنبه",
            "دوشنبه",
            "سه‌شنبه",
            "چهارشنبه",
            "پنج‌شنبه",
            "جمعه",
            "شنبه تا چهارشنبه (کف روزانه)",
        ]
        action_label = "اقدام عملیاتی"
        day_label = "روز هفته"
    else:
        days_list = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
            "Mon-Fri (Daily Floor)",
        ]
        action_label = "Next Action"
        day_label = "Day"

    days_yaml = "\n".join(f"      - {d}" for d in days_list) + "\n      - null"

    return {
        "Tasks.base": f"""filters:
  and:
    - file.inFolder("02-Tasks")
properties:
  action:
    displayName: {action_label}
  day:
    displayName: {day_label}
  status:
    displayName: Status
  pillar:
    displayName: Pillar
  cadence:
    displayName: Cadence
  sprint:
    displayName: Sprint
  priority:
    displayName: Priority
  project:
    displayName: Project
  area:
    displayName: Area
views:
  - type: kanban
    name: All Active Sprints
    filters:
      and:
        - status != "Backlog"
    groupBy:
      property: status
      direction: ASC
    groupOrder:
      - Doing
      - Sprint
      - Locked
      - Done
      - null
    order:
      - file.name
      - action
      - day
      - project
      - priority
  - type: kanban
    name: By Life Pillar
    filters:
      and:
        - status != "Done"
    groupBy:
      property: pillar
      direction: ASC
    groupOrder:
      - Projects
      - Content
      - Self
      - Family
      - null
    order:
      - file.name
      - action
      - cadence
      - status
      - priority
  - type: table
    name: Finite Open Loops
    filters:
      and:
        - cadence == "finite"
        - status != "Done"
    order:
      - file.name
      - action
      - pillar
      - project
      - status
      - priority
  - type: table
    name: Daily Floor
    filters:
      and:
        - cadence == "recurring"
    order:
      - file.name
      - action
      - day
      - pillar
      - status
  - type: table
    name: Master Table
    order:
      - file.name
      - pillar
      - cadence
      - project
      - day
      - sprint
      - status
      - priority
      - area
    sort:
      - property: pillar
        direction: ASC
""",
        "Today.base": f"""filters:
  and:
    - file.inFolder("02-Tasks")
    - today == true
    - status != "Done"
    - status != "Locked"
properties:
  action:
    displayName: {action_label}
  day:
    displayName: {day_label}
  status:
    displayName: Status
  cadence:
    displayName: Cadence
  pillar:
    displayName: Pillar
  project:
    displayName: Project
  priority:
    displayName: Priority
views:
  - type: table
    name: Today Table
    order:
      - file.name
      - action
      - day
      - status
      - project
  - type: cards
    name: Today Cards
    order:
      - file.name
      - action
      - day
      - status
      - project
""",
        "Weekly.base": f"""filters:
  and:
    - file.inFolder("02-Tasks")
    - or:
        - cadence == "recurring"
        - status == "Sprint"
        - status == "Doing"
    - status != "Done"
    - status != "Locked"
properties:
  action:
    displayName: {action_label}
  status:
    displayName: Status
  day:
    displayName: {day_label}
  pillar:
    displayName: Pillar
  project:
    displayName: Project
  priority:
    displayName: Priority
views:
  - type: kanban
    name: Weekly Board
    groupBy:
      property: day
      direction: ASC
    groupOrder:
{days_yaml}
    order:
      - file.name
      - action
      - project
      - priority
  - type: table
    name: Weekly Table
    order:
      - day
      - file.name
      - action
      - project
      - status
    sort:
      - property: day
        direction: ASC
""",
        "00-Focus/Cohorts.base": """filters:
  and:
    - file.inFolder("00-Focus/Cohorts")
properties:
  status:
    displayName: Status
  pillar:
    displayName: Pillar
  cadence_mode:
    displayName: Rhythm
  quota_target:
    displayName: Target Quota
  quota_completed:
    displayName: Completed
  end_date:
    displayName: Deadline
  project:
    displayName: Project
views:
  - type: kanban
    name: Cohorts by Pillar
    groupBy:
      property: pillar
      direction: ASC
    groupOrder:
      - Content
      - Self
      - Projects
      - Family
      - null
    order:
      - file.name
      - cadence_mode
      - quota_completed
      - quota_target
      - end_date
      - status
  - type: table
    name: Active Campaigns
    order:
      - file.name
      - pillar
      - project
      - cadence_mode
      - quota_completed
      - quota_target
      - end_date
      - status
""",
        "00-Focus/Feasibility.base": """filters:
  and:
    - file.inFolder("00-Focus/Feasibility")
properties:
  verdict:
    displayName: Verdict
  pillar:
    displayName: Pillar
  idea:
    displayName: Idea
  created:
    displayName: Created
views:
  - type: kanban
    name: Feasibility Pipeline
    groupBy:
      property: verdict
      direction: ASC
    order:
      - file.name
      - pillar
      - created
  - type: table
    name: All Briefs
    order:
      - file.name
      - verdict
      - pillar
      - created
""",
        "00-Focus/Pillars.base": """filters:
  and:
    - file.inFolder("00-Focus/Pillars")
properties:
  pillar:
    displayName: Pillar
  updated:
    displayName: Updated
views:
  - type: table
    name: All Pillars
    order:
      - file.name
      - pillar
      - updated
""",
        "00-Inbox/Ideas-Parking.base": """filters:
  and:
    - file.inFolder("00-Inbox/Ideas-Parking")
    - type != "moc"
properties:
  pillar:
    displayName: Pillar
  verdict:
    displayName: Status
  created:
    displayName: Created
views:
  - type: table
    name: Parked Ideas
    order:
      - file.name
      - pillar
      - verdict
      - created
""",
        "01-Projects/Projects.base": """filters:
  and:
    - file.inFolder("01-Projects")
    - type == "project"
properties:
  pillar:
    displayName: Pillar
  status:
    displayName: Status
  area:
    displayName: Area
  workspace:
    displayName: Workspace
views:
  - type: kanban
    name: Projects by Pillar
    groupBy:
      property: pillar
      direction: ASC
    groupOrder:
      - Projects
      - Content
      - Self
      - Family
      - null
    order:
      - file.name
      - status
      - area
  - type: table
    name: All Projects
    order:
      - file.name
      - pillar
      - status
      - area
      - workspace
""",
    }


def render_project_hub(
    name: str,
    workspace: str,
    pillar: str,
    today: str,
    parent: str = "",
    aliases: list[str] | None = None,
) -> str:
    task_folder = f"02-Tasks/{parent}/{name}" if parent else f"02-Tasks/{pillar}/{name}"
    ws_val = workspace.replace("\\", "\\\\") if workspace else ""
    parent_line = f'parent: "[[{parent}]]"\n' if parent else ""
    aliases_line = f"aliases: {json.dumps(aliases, ensure_ascii=False)}\n" if aliases else ""
    parent_hub_link = f" | Parent: [[{parent}]]" if parent else ""
    return f"""---
type: project
status: active
pillar: {pillar}
area: Product
{parent_line}{aliases_line}workspace: "{ws_val}"
updated: {today}
---

# {name}

> Hub: [[Projects MOC]] | Pillar: [[Pillars MOC]]{parent_hub_link}

## Live Task Board
```base
filters:
  and:
    - file.inFolder("{task_folder}")
properties:
  action:
    displayName: Next Action
  day:
    displayName: Day
  status:
    displayName: Status
  priority:
    displayName: Priority
views:
  - type: kanban
    name: Board
    groupBy:
      property: status
      direction: ASC
    groupOrder:
      - Doing
      - Sprint
      - Locked
      - Backlog
      - Done
      - null
    order:
      - file.name
      - action
      - priority
  - type: table
    name: Backlog & Table
    order:
      - file.name
      - status
      - action
      - priority
```

## Current Focus
- Run `/obsi-consult` from `{name}` to align Vision, Macro Scorecard, and Macro Focus Bundles.
"""


def render_pillar_note(pillar: str, today: str) -> str:
    return f"""---
type: pillar
pillar: {pillar}
updated: {today}
---

# Pillar: {pillar}

> Back to [[Pillars MOC]] | [[00-Home]]

## Live Tasks in `{pillar}`
```base
filters:
  and:
    - file.inFolder("02-Tasks")
    - pillar == "{pillar}"
properties:
  action:
    displayName: Next Action
  status:
    displayName: Status
  project:
    displayName: Project
views:
  - type: table
    name: Pillar Tasks
    order:
      - file.name
      - status
      - action
      - project
```
"""


def build_scaffold_files(
    lang: str,
    pillars: list[str],
    projects: list[tuple[str, str, str]],
    today: str,
) -> tuple[dict[str, str], list[str]]:
    month_str = today[:7]
    files: dict[str, str] = {}
    empty_dirs: list[str] = [
        "00-Focus/Cohorts",
        "00-Focus/Feasibility",
        "00-Focus/Scorecards",
        "00-Focus/Decisions",
        "03-Marketing",
    ]

    files[".gitignore"] = ".obsidian/workspace*.json\n.obsidian/cache\n.trash/\n.DS_Store\nThumbs.db\n"

    for rel, content in build_base_files(lang).items():
        files[rel] = content

    project_links = " · ".join(f"[[{name}]]" for name, _, _ in projects) or "*(Run `/obsi-setup` to add your first project)*"
    pillar_rows = "\n".join(f"| **{p}** | Define primary outcome | `[[00-Home]]` |" for p in pillars)

    if lang == "fa":
        home_title = "# 🧠 Brain HQ — ستاد فرماندهی پروژه‌ها و اجرا"
        home_sub = "> معماری **SSOT · Native Obsidian Bases** — تمام ویوها خودکار از فایل‌های واقعی ساخته می‌شوند."
        sec_today = "## ☀️ ۱. اجرای امروز ([[Today.base]])"
        sec_week = "## 🗓️ ۲. برنامه هفتگی ([[Weekly.base]])"
        sec_cohorts = "## 🧪 ۳. کورس‌های مقید به زمان ([[Cohorts.base]])"
        sec_nav = "## ⚡ دسترسی سریع"
        sec_proj = "## 🚀 پروژه‌ها"
    else:
        home_title = "# 🧠 Brain HQ — Founder Operating System"
        home_sub = "> **SSOT · Native Obsidian Bases** — Every view updates automatically from live project, cohort, and task notes."
        sec_today = "## ☀️ 1. Today Queue ([[Today.base]])"
        sec_week = "## 🗓️ 2. Weekly Schedule ([[Weekly.base]])"
        sec_cohorts = "## 🧪 3. Active Time-Boxed Cohorts ([[Cohorts.base]])"
        sec_nav = "## ⚡ Quick Navigation"
        sec_proj = "## 🚀 Projects"

    files["00-Home.md"] = f"""---
type: home
updated: {today}
---

{home_title}

{home_sub}

---

{sec_today}
![[Today.base]]

---

{sec_week}
![[Weekly.base]]

---

{sec_cohorts}
![[Cohorts.base]]

---

{sec_nav}
- 🌟 [[00-North-Star]] | 🏛️ [[Pillars MOC]] ([[Pillars.base]])
- 🗓️ [[{month_str} - Monthly Focus]] | 🎯 [[Tasks.base]]
- 🅿️ [[Ideas-Parking]] ([[Ideas-Parking.base]]) | [[Feasibility.base]]
- 🗂️ [[Projects MOC]] ([[Projects.base]]) | 📣 [[Marketing MOC]]
- 📥 [[Quick Capture]] | 📊 `00-Focus/Scorecards/` · `00-Focus/Decisions/` | 🤖 [[AGENTS]]

---

{sec_proj}
- {project_links}
"""

    files["AGENTS.md"] = f"""---
type: system
updated: {today}
---

# Brain Vault — AI Agent Operating Protocol (SSOT + Native Bases)

1. Confirm target layer/file before writing or editing Vault notes.
2. Enforce SSOT: keep Cockpit in `00-Home.md` 100% live-driven via `.base` embeds; keep Cohort logs inside `00-Focus/Cohorts/`; keep macro project Scorecards in `00-Focus/Scorecards/`.
3. Use 5-layer Hub-and-Spoke commands: `/obsi` (hub & daily execution), `/obsi-setup`, `/obsi-consult`, `/obsi-priority`, `/obsi-inspect`.
"""

    files["00-Focus/00-North-Star.md"] = f"""---
type: north-star
updated: {today}
---

# 🌟 North Star & Pillars

> Back to [[00-Home]] | Pillars: [[Pillars MOC]] | Monthly Plan: [[{month_str} - Monthly Focus]]

| Pillar | Primary Why | Outcome |
| :--- | :--- | :--- |
{pillar_rows}

## Blind Spots Log
- [ ] Run `/obsi-consult` on your primary project to establish its Macro Market Scorecard.
"""

    files[f"00-Focus/Monthly-Plans/{month_str} - Monthly Focus.md"] = f"""---
type: monthly-plan
month: {month_str}
status: active
updated: {today}
---

# 🗓️ Monthly Focus: `{month_str}`

> Back to [[00-Home]] | [[Pillars MOC]] | [[Tasks.base]]

## Active Projects & Milestones
- {project_links}

## Active Cohorts & Daily Floor
> Linked to [[Cohorts.base]]:
- *(Select Cohorts via `/obsi-priority` after locking project Visions in `/obsi-consult`)*
"""

    for idx, pillar in enumerate(pillars, 1):
        files[f"00-Focus/Pillars/{idx}-{pillar}.md"] = render_pillar_note(pillar, today)
        empty_dirs.append(f"02-Tasks/{pillar}")

    for name, ws, pillar in projects:
        clean_name = slugify_project(name)
        files[f"01-Projects/{clean_name}.md"] = render_project_hub(clean_name, ws, pillar, today)
        empty_dirs.append(f"02-Tasks/{pillar}/{clean_name}")

    files["00-Inbox/Quick Capture.md"] = f"""---
type: inbox
updated: {today}
---

# 📥 Quick Capture

Drop raw thoughts here or say `obsi <thought>` in chat to route cleanly into the right Vault layer.
"""

    files["00-Inbox/Ideas-Parking/Ideas-Parking.md"] = f"""---
type: moc
updated: {today}
---

# 🅿️ Ideas Parking

> View all parked ideas in [[Ideas-Parking.base]] or evaluate with `/obsi-consult`.
"""

    files["04-MOCs/Pillars MOC.md"] = f"""---
type: moc
updated: {today}
---

# 🏛️ Pillars MOC
![[Pillars.base]]
"""

    files["04-MOCs/Projects MOC.md"] = f"""---
type: moc
updated: {today}
---

# 🗂️ Projects MOC
![[Projects.base]]
"""

    files["04-MOCs/Marketing MOC.md"] = f"""---
type: moc
updated: {today}
---

# 📣 Marketing MOC
Store project marketing briefs and distribution playbooks under `03-Marketing/`.
"""

    # Native Core Templates (zero Templater syntax, zero broken wikilinks)
    files["05-Resources/Templates/Task Template.md"] = """---
type: task
pillar: Projects
cadence: finite
project: "[[<Project>]]"
sprint: ""
status: Backlog
action: "Define concrete 1-3h action"
day: ""
depends_on: ""
today: false
priority: High
area: Product
created: {{date}}
---

# {{title}}

## Done Criteria
- [ ] 
"""

    files["05-Resources/Templates/Project Template.md"] = """---
type: project
status: active
pillar: Projects
area: Product
workspace: ""
updated: {{date}}
---

# {{title}}

```base
filters:
  and:
    - file.inFolder("02-Tasks")
    - contains(project, this.file.name)
views:
  - type: kanban
    name: Board
    groupBy:
      property: status
      direction: ASC
    groupOrder:
      - Doing
      - Sprint
      - Locked
      - Backlog
      - Done
      - null
```
"""

    files["05-Resources/Templates/Cohort Template.md"] = """---
type: cohort
pillar: Projects
project: "[[<Project>]]"
title: "{{title}}"
cadence_mode: milestone_driven
schedule_days: [Flexible]
quota_target: 10
quota_completed: 0
start_date: {{date}}
end_date: ""
checkpoints: [3, 6, 10]
status: Active
created: {{date}}
---

# Cohort: {{title}}

## Hypothesis & Gate Verdict (`Scale / Pivot / Kill`)
- 🟢 **Scale:**
- 🟡 **Pivot:**
- 🔴 **Kill:**
"""

    files["05-Resources/Templates/Scorecard Template.md"] = """---
type: scorecard
project: "[[{{title}}]]"
stage: ""
last_full_audit: {{date}}
active_deep_dive: ""
updated: {{date}}
---

# 📊 Scorecard: `{{title}}`

## 🎯 Vision & Stage
- **Stage:** 

## 📊 Macro Gap Scorecard
| Success Pillar | Status | Progress + Evidence | Gap | Priority |
| :--- | :---: | :--- | :--- | :---: |
| | ⬜ | | | |

## 🎯 Macro Focus Bundles
- **Bundle 1:** **Main Aspect:** ... · *Keep in mind alongside:* ...

## 🧭 Active Deep-Dive
- **Current Stage:**

## 🕵️ Inspector Audit
- *(Pending)*
"""

    files["05-Resources/Templates/Monthly Focus Template.md"] = """---
type: monthly-plan
month: YYYY-MM
status: active
updated: {{date}}
---

# 🗓️ Monthly Focus: `YYYY-MM`

> Back to [[00-Home]] | [[Pillars MOC]] | [[Tasks.base]]

## Active Commitments
1. [[<Project 1>]] — milestone

## Active Cohorts
- [[<Cohort 1>]]
"""

    for d in empty_dirs:
        files[f"{d}/.gitkeep"] = ""

    return files, empty_dirs


def parse_project_specs(raw: str, default_pillar: str) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for item in [x.strip() for x in raw.split(",") if x.strip()]:
        parts = [p.strip() for p in item.split("|")]
        name = slugify_project(parts[0])
        ws = parts[1] if len(parts) > 1 else ""
        pillar = parts[2] if len(parts) > 2 and parts[2] else default_pillar
        out.append((name, ws, pillar))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold a Native Obsidian Bases Second Brain Vault.")
    parser.add_argument("--vault", required=True, help="Target Obsidian Vault directory")
    parser.add_argument("--lang", choices=["en", "fa"], default="en", help="Calendar/template language")
    parser.add_argument("--pillars", default="Projects,Content,Self,Family", help="Comma-separated pillar names")
    parser.add_argument("--projects", default="", help="Comma-separated `Name|workspace|Pillar` entries")
    parser.add_argument("--add-project", default="", help="Add single `Name|workspace|Pillar` into existing Vault")
    parser.add_argument("--parent", default="", help="Optional parent umbrella project name for --add-project")
    parser.add_argument("--aliases", default="", help="Optional comma-separated aliases for --add-project")
    parser.add_argument("--scan-workspace", default="", help="Inspect registered projects & unregistered subfolders in workspace (read-only)")
    parser.add_argument("--config-out", default="", help="Optional path to write brain-os.json")
    parser.add_argument("--playbooks-dir", default="", help="Playbooks directory recorded in config-out")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without mutating disk")
    parser.add_argument("--apply", action="store_true", help="Write planned files cleanly (skips existing)")
    parser.add_argument("--git-init", action="store_true", help="Initialize git repo (`git init -b main`) if missing")
    args = parser.parse_args()

    vault = os.path.abspath(args.vault)
    if args.scan_workspace:
        print(json.dumps(scan_workspace_subfolders(vault, args.scan_workspace), ensure_ascii=False, indent=2))
        return

    today = datetime.date.today().isoformat()
    pillars = [p.strip() for p in args.pillars.split(",") if p.strip()] or ["Projects", "Content", "Self", "Family"]
    default_pillar = pillars[0]

    planned: dict[str, str] = {}
    if args.add_project:
        parent = slugify_project(args.parent) if args.parent.strip() else ""
        aliases = [a.strip() for a in re.split(r"[,،]", args.aliases) if a.strip()] if args.aliases.strip() else None
        for name, ws, pillar in parse_project_specs(args.add_project, default_pillar):
            proj_rel = f"01-Projects/{parent}/{name}.md" if parent else f"01-Projects/{name}.md"
            task_rel = f"02-Tasks/{parent}/{name}/.gitkeep" if parent else f"02-Tasks/{pillar}/{name}/.gitkeep"
            planned[proj_rel] = render_project_hub(name, ws, pillar, today, parent=parent, aliases=aliases)
            planned[task_rel] = ""
    else:
        projects = parse_project_specs(args.projects, default_pillar)
        planned, _ = build_scaffold_files(args.lang, pillars, projects, today)

    created: list[str] = []
    skipped_existing: list[str] = []

    if args.apply:
        os.makedirs(vault, exist_ok=True)
        for rel, content in sorted(planned.items()):
            abs_p = os.path.join(vault, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(abs_p), exist_ok=True)
            if os.path.exists(abs_p):
                skipped_existing.append(rel)
                continue
            with open(abs_p, "w", encoding="utf-8") as f:
                f.write(content)
            created.append(rel)

        if args.config_out:
            os.makedirs(os.path.dirname(os.path.abspath(args.config_out)), exist_ok=True)
            cfg_payload = {
                "vault_path": vault,
                "playbooks_dir": args.playbooks_dir or os.path.expanduser(
                    os.path.join("~", ".gemini", "config", "skills", "obsi-consult", "playbooks")
                ),
                "language": args.lang,
                "calendar": "sat-fri" if args.lang == "fa" else "mon-sun",
                "scorecards_dir": "00-Focus/Scorecards",
                "decisions_dir": "00-Focus/Decisions",
                "cache_ttl_days": 90,
            }
            with open(args.config_out, "w", encoding="utf-8") as f:
                json.dump(cfg_payload, f, ensure_ascii=False, indent=2)
                f.write("\n")

        if args.git_init and not os.path.exists(os.path.join(vault, ".git")):
            subprocess.run(["git", "-C", vault, "init", "-b", "main"], check=True, capture_output=True)

    summary = {
        "mode": "apply" if args.apply else "dry_run",
        "vault": vault,
        "lang": args.lang,
        "total_planned": len(planned),
        "created_count": len(created),
        "skipped_existing_count": len(skipped_existing),
        "config_written": args.config_out if (args.apply and args.config_out) else None,
        "planned_files": sorted(planned.keys()) if not args.apply else created,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
