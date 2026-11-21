#!/usr/bin/env python3
"""
resolve_obsi_hub.py
Thin Hub resolver for /obsi: checks brain-os.json & Vault presence,
detects active project(s) from cwd (supporting monorepos/multi-project workspaces,
unregistered subfolder discovery, and bilingual aliases), summarizes live stats,
and returns ready-to-render 5-layer Hub options for ask_question.
"""
import argparse
import json
import os
import re
import sys
import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_CONFIG_PATH = os.path.expanduser(os.path.join("~", ".gemini", "config", "brain-os.json"))
FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
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


def load_config(config_path: str | None = None) -> tuple[dict, bool]:
    path = config_path or DEFAULT_CONFIG_PATH
    if not path or not os.path.exists(path):
        return {}, False
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            loaded = json.load(f)
        return (loaded if isinstance(loaded, dict) else {}), True
    except Exception:
        return {}, False


def parse_frontmatter(txt: str) -> dict:
    m = FM_RE.match(txt)
    if not m:
        return {}
    try:
        data = yaml.safe_load(m.group(1))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def parse_aliases(raw) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str):
        return [x.strip() for x in re.split(r"[,،]", raw) if x.strip()]
    return []


def _extract_link_stem(raw) -> str:
    txt = str(raw or "").strip()
    if not txt:
        return ""
    m = WIKILINK_RE.search(txt)
    return m.group(1).strip() if m else txt


def _norm_path(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def scan_projects(vault_path: str, scorecards_rel: str = "00-Focus/Scorecards") -> list[dict]:
    projects_dir = os.path.join(vault_path, "01-Projects")
    scorecards_dir = os.path.join(vault_path, scorecards_rel.replace("/", os.sep))
    items: list[dict] = []
    if not os.path.isdir(projects_dir):
        return items
    for root, _, files in os.walk(projects_dir):
        for fn in sorted(files):
            if not fn.endswith(".md"):
                continue
            fp = os.path.join(root, fn)
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                fm = parse_frontmatter(f.read())
            if fm.get("type") != "project":
                continue
            name = os.path.splitext(fn)[0]
            items.append(
                {
                    "name": name,
                    "path": fp,
                    "workspace": str(fm.get("workspace") or "").strip(),
                    "parent": _extract_link_stem(fm.get("parent")),
                    "aliases": parse_aliases(fm.get("aliases")),
                    "pillar": str(fm.get("pillar") or "").strip(),
                    "status": str(fm.get("status") or "").strip(),
                    "cohort": _extract_link_stem(fm.get("cohort")),
                    "has_scorecard": os.path.exists(os.path.join(scorecards_dir, f"{name}.md")),
                }
            )
    return items


def resolve_project_query(query: str, projects: list[dict]) -> dict | None:
    q = str(query or "").strip().lower()
    if not q or not projects:
        return None
    for p in projects:
        if p["name"].lower() == q:
            return p
    for p in projects:
        if any(a.lower() == q for a in p.get("aliases") or []):
            return p
    ws_matches = [
        p
        for p in projects
        if p.get("workspace") and os.path.basename(_norm_path(p["workspace"])).lower() == q
    ]
    if len(ws_matches) == 1:
        return ws_matches[0]
    return None


def discover_unregistered_subfolders(cwd: str, projects: list[dict]) -> list[dict]:
    if not cwd or not os.path.isdir(cwd):
        return []
    reg_ws = [_norm_path(p["workspace"]) for p in projects if p.get("workspace")]
    out: list[dict] = []
    try:
        entries = list(os.scandir(cwd))
    except OSError:
        return []
    for entry in entries:
        try:
            if not entry.is_dir():
                continue
        except OSError:
            continue
        if entry.name.startswith(".") or entry.name.lower() in IGNORE_WORKSPACE_DIRS:
            continue
        entry_norm = _norm_path(entry.path)
        if any(ws == entry_norm or ws.startswith(entry_norm + os.sep) for ws in reg_ws):
            continue
        is_git = os.path.isdir(os.path.join(entry.path, ".git"))
        out.append({"name": entry.name, "path": os.path.abspath(entry.path), "is_git_repo": is_git})
    out.sort(key=lambda d: (not d["is_git_repo"], d["name"].lower()))
    return out


def detect_workspace_projects(
    projects: list[dict], cwd: str
) -> tuple[dict | None, list[dict], str | None]:
    if not cwd or not projects:
        return None, [], None

    cwd_norm = _norm_path(cwd)
    anc_candidates: list[tuple[int, dict, str]] = []
    descendants: list[dict] = []

    for p in projects:
        ws = str(p.get("workspace") or "").strip()
        if not ws:
            continue
        ws_norm = _norm_path(ws)
        if cwd_norm == ws_norm or cwd_norm.startswith(ws_norm + os.sep):
            anc_candidates.append((len(ws_norm), p, ws_norm))
        elif ws_norm.startswith(cwd_norm + os.sep):
            descendants.append(p)

    exact_or_ancestor: list[dict] = []
    exact_names_low: set[str] = set()
    if anc_candidates:
        max_len = max(item[0] for item in anc_candidates)
        for length, p, ws_norm in anc_candidates:
            if length == max_len:
                exact_or_ancestor.append(p)
                if ws_norm == cwd_norm:
                    exact_names_low.add(p["name"].lower())

    parent_children: list[dict] = []
    if exact_names_low:
        for p in projects:
            parent_low = str(p.get("parent") or "").strip().lower()
            if parent_low and parent_low in exact_names_low:
                parent_children.append(p)

    matched: list[dict] = []
    seen_names: set[str] = set()
    for p in exact_or_ancestor + descendants + parent_children:
        key = p["name"].lower()
        if key not in seen_names:
            seen_names.add(key)
            matched.append(p)

    matched_low = {p["name"].lower() for p in matched}
    umbrella_name: str | None = None
    if len(matched) > 1:
        for p in exact_or_ancestor:
            ws = str(p.get("workspace") or "").strip()
            if not ws or _norm_path(ws) != cwd_norm:
                continue
            if p.get("parent"):
                continue
            p_low = p["name"].lower()
            has_child = any(str(m.get("parent") or "").lower() == p_low for m in matched if m is not p)
            if has_child or any(_norm_path(m["workspace"]).startswith(cwd_norm + os.sep) for m in matched if m.get("workspace")):
                if p_low in matched_low:
                    umbrella_name = p["name"]
                    break

    if len(matched) == 1:
        return matched[0], matched, None
    if len(matched) > 1:
        return None, matched, umbrella_name

    base = os.path.basename(cwd_norm)
    base_matches = [
        p
        for p in projects
        if p["name"].lower() == base or any(a.lower() == base for a in p.get("aliases") or [])
    ]
    if len(base_matches) == 1:
        return base_matches[0], base_matches, None
    return None, [], None


def detect_project(vault_path: str, cwd: str) -> tuple[str | None, int]:
    projects = scan_projects(vault_path)
    single, _, _ = detect_workspace_projects(projects, cwd)
    return (single["name"] if single else None), len(projects)


def count_vault_stats(vault_path: str) -> dict:
    today_tasks = 0
    sprint_tasks = 0
    active_cohorts = 0
    scorecards_count = 0

    tasks_dir = os.path.join(vault_path, "02-Tasks")
    if os.path.isdir(tasks_dir):
        for root, _, files in os.walk(tasks_dir):
            for fn in files:
                if not fn.endswith(".md"):
                    continue
                with open(os.path.join(root, fn), "r", encoding="utf-8", errors="replace") as f:
                    fm = parse_frontmatter(f.read())
                status = str(fm.get("status") or "")
                if fm.get("today") is True and status not in ("Done", "Locked"):
                    today_tasks += 1
                if status in ("Sprint", "Doing"):
                    sprint_tasks += 1

    cohorts_dir = os.path.join(vault_path, "00-Focus", "Cohorts")
    if os.path.isdir(cohorts_dir):
        for fn in os.listdir(cohorts_dir):
            if fn.endswith(".md"):
                with open(os.path.join(cohorts_dir, fn), "r", encoding="utf-8", errors="replace") as f:
                    fm = parse_frontmatter(f.read())
                if str(fm.get("status") or "") in ("Active", "Pulse-Check"):
                    active_cohorts += 1

    sc_dir = os.path.join(vault_path, "00-Focus", "Scorecards")
    if os.path.isdir(sc_dir):
        scorecards_count = sum(1 for fn in os.listdir(sc_dir) if fn.endswith(".md"))

    return {
        "today_tasks": today_tasks,
        "sprint_tasks": sprint_tasks,
        "active_cohorts": active_cohorts,
        "scorecards_count": scorecards_count,
    }


def _truncate_words(text: str, max_len: int = 84) -> str:
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1].rstrip()
    if " " in cut:
        head = cut.rsplit(" ", 1)[0].rstrip(" ,،.;:-—")
        if head:
            cut = head
    return cut + "…"


def collect_project_tasks(
    vault_path: str,
    project_name: str,
    lang: str = "en",
    limit: int = 5,
    child_names: list[str] | None = None,
) -> tuple[dict, str]:
    tasks_dir = os.path.join(vault_path, "02-Tasks")
    active_rows: list[tuple[tuple[int, int, str], dict]] = []
    locked_count = 0
    backlog_count = 0
    target_names = {project_name.strip().lower()}
    if child_names:
        target_names.update(c.strip().lower() for c in child_names if str(c).strip())
    target_names.discard("")

    if os.path.isdir(tasks_dir) and target_names:
        for root, _, files in os.walk(tasks_dir):
            for fn in sorted(files):
                if not fn.endswith(".md"):
                    continue
                fp = os.path.join(root, fn)
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    fm = parse_frontmatter(f.read())
                if fm.get("type") and str(fm.get("type")).lower() != "task":
                    continue

                proj_raw = str(fm.get("project") or "").strip()
                m = WIKILINK_RE.search(proj_raw)
                proj_stem = m.group(1).strip() if m else proj_raw
                rel_parts = os.path.relpath(fp, tasks_dir).replace("\\", "/").split("/")
                matched = (
                    proj_stem.lower() in target_names
                    if proj_stem
                    else any(part.lower() in target_names for part in rel_parts[:-1])
                )
                if not matched:
                    continue

                status = str(fm.get("status") or "").strip()
                if status.lower() == "done":
                    continue

                today_flag = fm.get("today") is True
                priority = str(fm.get("priority") or "").strip()
                action = " ".join(str(fm.get("action") or "").split())
                clean_title = os.path.splitext(fn)[0]
                prefix_candidates = [project_name] + (list(child_names) if child_names else [])
                for cand in prefix_candidates:
                    stripped_title = clean_title
                    for sep in (" - ", " — ", "- ", ": "):
                        pref = f"{cand}{sep}"
                        if clean_title.lower().startswith(pref.lower()) and len(clean_title) > len(pref):
                            stripped_title = clean_title[len(pref):].strip()
                            break
                    if stripped_title != clean_title:
                        clean_title = stripped_title
                        break

                if status == "Locked":
                    locked_count += 1
                elif status in ("Sprint", "Doing") or today_flag:
                    is_hot = today_flag or status == "Doing"
                    badge = "🔥" if is_hot else "⚡"
                    short_action = _truncate_words(action, 84)
                    sort_key = (0 if is_hot else 1, PRIORITY_RANK.get(priority.lower(), 3), clean_title.lower())
                    active_rows.append(
                        (
                            sort_key,
                            {
                                "badge": badge,
                                "title": clean_title,
                                "action": short_action,
                                "status": status or "Backlog",
                                "priority": priority,
                                "today": today_flag,
                                "path": fp,
                            },
                        )
                    )
                else:
                    backlog_count += 1

    active_rows.sort(key=lambda pair: pair[0])
    active_total = len(active_rows)
    today_count = sum(1 for _, item in active_rows if item["today"])
    shown_items = [pair[1] for pair in active_rows[: max(0, limit)]]
    more_active = max(0, active_total - len(shown_items))

    if lang == "fa":
        header = (
            f"📌 تسک‌های فعال «{project_name}» ({active_total} باز):"
            if active_total > 0
            else f"📌 تسک فعالی برای «{project_name}» باز نیست."
        )
    else:
        header = (
            f"📌 Active tasks for {project_name} ({active_total} open):"
            if active_total > 0
            else f"📌 No active tasks open for {project_name}."
        )

    lines = [header]
    for item in shown_items:
        line = f"• {item['badge']} {item['title']}"
        if item["action"]:
            line += f" — {item['action']}"
        lines.append(line)

    footer_parts: list[str] = []
    if lang == "fa":
        if more_active:
            footer_parts.append(f"➕ {more_active} فعال دیگر")
        if locked_count:
            footer_parts.append(f"🔒 {locked_count} قفل")
        if backlog_count:
            footer_parts.append(f"📋 {backlog_count} بک‌لاگ")
    else:
        if more_active:
            footer_parts.append(f"+{more_active} more active")
        if locked_count:
            footer_parts.append(f"🔒 {locked_count} locked")
        if backlog_count:
            footer_parts.append(f"📋 {backlog_count} backlog")
    if footer_parts:
        lines.append(" · ".join(footer_parts))

    summary = {
        "project": project_name,
        "active_total": active_total,
        "today_count": today_count,
        "shown_count": len(shown_items),
        "more_active": more_active,
        "locked_count": locked_count,
        "backlog_count": backlog_count,
        "items": shown_items,
    }
    return summary, "\n".join(lines)


def _format_project_entry(p: dict, lang: str) -> str:
    parts: list[str] = []
    if p["is_umbrella"]:
        parts.append("کل مجموعه" if lang == "fa" else "umbrella")
    if lang == "fa":
        if p["today_count"]:
            parts.append(f"🔥 {p['today_count']} امروز")
        if p["active_total"]:
            parts.append(f"{p['active_total']} فعال")
        if p["locked_count"]:
            parts.append(f"🔒 {p['locked_count']} قفل")
        if p["backlog_count"]:
            parts.append(f"📋 {p['backlog_count']} بک‌لاگ")
        if not (p["active_total"] or p["locked_count"] or p["backlog_count"]):
            parts.append("بدون تسک فعال")
    else:
        if p["today_count"]:
            parts.append(f"🔥 {p['today_count']} today")
        if p["active_total"]:
            parts.append(f"{p['active_total']} active")
        if p["locked_count"]:
            parts.append(f"🔒 {p['locked_count']} locked")
        if p["backlog_count"]:
            parts.append(f"📋 {p['backlog_count']} backlog")
        if not (p["active_total"] or p["locked_count"] or p["backlog_count"]):
            parts.append("no active tasks")
    return " · ".join(parts)


def resolve_hub(
    cwd: str = "",
    config_path: str | None = None,
    vault_override: str = "",
    max_tasks: int = 5,
    explicit_project: str = "",
) -> dict:
    cfg, cfg_exists = load_config(config_path)
    vault_path = vault_override or str(cfg.get("vault_path") or "")
    lang = str(cfg.get("language") or "en").lower()
    scorecards_rel = str(cfg.get("scorecards_dir") or "00-Focus/Scorecards")
    home_file = os.path.join(vault_path, "00-Home.md") if vault_path else ""

    if (not cfg_exists and not vault_override) or not vault_path or not os.path.exists(home_file):
        if lang == "fa":
            summary = "هنوز مغز دوم ابسیدین پیکربندی نشده است.\nبا چند سوال ساده کل ساختار پوشه‌ها، بوردهای زنده و پروژه‌هایت را می‌سازم."
            opts = ["(Recommended) شروع ویزارد راه‌اندازی ابسیدین (/obsi-setup)"]
        else:
            summary = "No Second Brain Vault is configured yet.\nI will scaffold your Native Obsidian Bases Vault and projects in 4 quick questions."
            opts = ["(Recommended) Launch Obsidian Brain setup wizard (/obsi-setup)"]
        return {
            "state": "needs_setup",
            "workspace_mode": "needs_setup",
            "vault_path": vault_path or None,
            "detected_project": None,
            "umbrella_project": None,
            "workspace_projects": [],
            "unregistered_subfolders": [],
            "stats": {},
            "project_tasks": None,
            "project_tasks_card": "",
            "summary_2lines": summary,
            "recommended_options": opts,
        }

    projects = scan_projects(vault_path, scorecards_rel=scorecards_rel)
    stats = count_vault_stats(vault_path)
    stats["projects_count"] = len(projects)
    unregistered = discover_unregistered_subfolders(cwd, projects)

    resolved_explicit = resolve_project_query(explicit_project, projects) if explicit_project.strip() else None
    umbrella_name: str | None = None
    if resolved_explicit:
        matched = [resolved_explicit]
    else:
        _, matched, umbrella_name = detect_workspace_projects(projects, cwd)

    if len(matched) > 1:
        ws_entries: list[dict] = []
        child_names_for_umbrella = [
            p["name"] for p in matched if not umbrella_name or p["name"].lower() != umbrella_name.lower()
        ]
        for p in matched:
            is_umb = bool(umbrella_name and p["name"].lower() == umbrella_name.lower())
            children = child_names_for_umbrella if is_umb else None
            t_summary, _ = collect_project_tasks(
                vault_path, p["name"], lang=lang, limit=max_tasks, child_names=children
            )
            ws_entries.append(
                {
                    "name": p["name"],
                    "workspace": p["workspace"],
                    "parent": p["parent"],
                    "aliases": p["aliases"],
                    "pillar": p["pillar"],
                    "is_umbrella": is_umb,
                    "active_total": t_summary["active_total"],
                    "today_count": t_summary["today_count"],
                    "locked_count": t_summary["locked_count"],
                    "backlog_count": t_summary["backlog_count"],
                    "has_scorecard": p["has_scorecard"],
                }
            )
        ws_entries.sort(
            key=lambda x: (
                1 if x["is_umbrella"] else 0,
                -x["today_count"],
                -x["active_total"],
                x["name"].lower(),
            )
        )

        unreg_count = len(unregistered)
        if lang == "fa":
            extra_unreg = f" · {unreg_count} پوشه ثبت‌نشده" if unreg_count else ""
            summary = (
                f"این ورک‌اسپیس چندپروژه‌ای است ({len(matched)} پروژه ثبت‌شده{extra_unreg}).\n"
                f"آمار کل مغز: {stats['today_tasks']} تسک امروز · {stats['sprint_tasks']} تسک اسپرینت · {stats['active_cohorts']} کورس فعال · {stats['scorecards_count']} کارنامه."
            )
            card_lines = [f"🗂️ پروژه‌های همین ورک‌اسپیس ({len(ws_entries)}):"]
            for entry in ws_entries:
                icon = "🔥" if entry["today_count"] else ("⚡" if entry["active_total"] else ("🌐" if entry["is_umbrella"] else "•"))
                card_lines.append(f"• {icon} {entry['name']} — {_format_project_entry(entry, lang)}")
            if unregistered:
                shown_unreg = [
                    f"{u['name']} (git)" if u["is_git_repo"] else u["name"]
                    for u in unregistered[:8]
                ]
                more_u = f" (+{unreg_count - 8})" if unreg_count > 8 else ""
                card_lines.append(
                    f"📁 پوشه‌های ثبت‌نشده قابل تبدیل به پروژه: {', '.join(shown_unreg)}{more_u}"
                )

            options = []
            for idx, entry in enumerate(ws_entries):
                pref = "(Recommended) " if idx == 0 else ""
                options.append(f"{pref}{entry['name']} ({_format_project_entry(entry, lang)})")
            if unregistered:
                options.append("➕ ثبت پوشه دیگر از همین ورک‌اسپیس به عنوان پروژه جدا (/obsi-setup)")
            else:
                options.append("لایه ۰ — مدیریت پروژه‌ها یا ستون‌ها (/obsi-setup)")
            options.append("لایه ۴ — بازرس چت و سلامت ابسیدین (/obsi-inspect)")
        else:
            extra_unreg = f" · {unreg_count} unregistered folder(s)" if unreg_count else ""
            summary = (
                f"Multi-project workspace detected ({len(matched)} registered{extra_unreg}).\n"
                f"Vault stats: {stats['today_tasks']} today · {stats['sprint_tasks']} sprint · {stats['active_cohorts']} active cohorts · {stats['scorecards_count']} scorecards."
            )
            card_lines = [f"🗂️ Projects in this workspace ({len(ws_entries)}):"]
            for entry in ws_entries:
                icon = "🔥" if entry["today_count"] else ("⚡" if entry["active_total"] else ("🌐" if entry["is_umbrella"] else "•"))
                card_lines.append(f"• {icon} {entry['name']} — {_format_project_entry(entry, lang)}")
            if unregistered:
                shown_unreg = [
                    f"{u['name']} (git)" if u["is_git_repo"] else u["name"]
                    for u in unregistered[:8]
                ]
                more_u = f" (+{unreg_count - 8})" if unreg_count > 8 else ""
                card_lines.append(
                    f"📁 Unregistered folders ready to add: {', '.join(shown_unreg)}{more_u}"
                )

            options = []
            for idx, entry in enumerate(ws_entries):
                pref = "(Recommended) " if idx == 0 else ""
                options.append(f"{pref}{entry['name']} ({_format_project_entry(entry, lang)})")
            if unregistered:
                options.append("➕ Register another subfolder from this workspace as a separate project (/obsi-setup)")
            else:
                options.append("Layer 0 — Manage Projects or Pillars (/obsi-setup)")
            options.append("Layer 4 — In-Flight Transcript & Vault Inspector (/obsi-inspect)")

        return {
            "state": "pick_project",
            "workspace_mode": "multi_project",
            "vault_path": vault_path,
            "detected_project": None,
            "umbrella_project": umbrella_name,
            "workspace_projects": ws_entries,
            "unregistered_subfolders": unregistered,
            "stats": stats,
            "project_tasks": None,
            "project_tasks_card": "\n".join(card_lines),
            "summary_2lines": summary,
            "recommended_options": options,
        }

    detected_proj = matched[0] if len(matched) == 1 else None
    detected = detected_proj["name"] if detected_proj else None
    workspace_mode = "single_project" if detected_proj else "global"

    project_tasks = None
    project_tasks_card = ""
    ws_entries = []
    if detected_proj:
        children = [
            p["name"]
            for p in projects
            if str(p.get("parent") or "").lower() == detected_proj["name"].lower()
        ]
        project_tasks, project_tasks_card = collect_project_tasks(
            vault_path, detected_proj["name"], lang=lang, limit=max_tasks, child_names=children or None
        )
        ws_entries = [
            {
                "name": detected_proj["name"],
                "workspace": detected_proj["workspace"],
                "parent": detected_proj["parent"],
                "aliases": detected_proj["aliases"],
                "pillar": detected_proj["pillar"],
                "is_umbrella": bool(children),
                "active_total": project_tasks["active_total"],
                "today_count": project_tasks["today_count"],
                "locked_count": project_tasks["locked_count"],
                "backlog_count": project_tasks["backlog_count"],
                "has_scorecard": detected_proj["has_scorecard"],
            }
        ]

    top = project_tasks["items"][0] if (project_tasks and project_tasks.get("items")) else None
    if lang == "fa":
        proj_label = f"پروژه فعال: «{detected}»" if detected else f"{len(projects)} پروژه در ابسیدین"
        summary = (
            f"مغز دوم آماده است ({proj_label}).\n"
            f"آمار زنده: {stats['today_tasks']} تسک امروز · {stats['sprint_tasks']} تسک اسپرینت · {stats['active_cohorts']} کورس فعال · {stats['scorecards_count']} کارنامه."
        )
        total_items = len(project_tasks["items"]) if project_tasks and project_tasks.get("items") else 0
        opt1 = (
            f"(Recommended) انجام {top['badge']} {top['title']} — یا انتخاب از بین {total_items} تسک فعال (/obsi next / done)"
            if top
            else "(Recommended) لایه ۳ — اجرای روزمره (ثبت پیشرفت / کار بعدی / برنامه هفته / بستن تسک)"
        )
        options = [
            opt1,
            "لایه ۱ — مشاور کلان بازار پروژه (/obsi-consult)",
            "لایه ۲ — انتخاب کورس‌ها و اولویت‌بندی (/obsi-priority)",
            "لایه ۰ — افزودن پروژه یا ستون جدید (/obsi-setup)",
            "لایه ۴ — بازرس چت و سلامت ابسیدین (/obsi-inspect)",
        ]
    else:
        proj_label = f"Active project: {detected}" if detected else f"{len(projects)} project(s) in Vault"
        summary = (
            f"Second Brain is ready ({proj_label}).\n"
            f"Live stats: {stats['today_tasks']} today · {stats['sprint_tasks']} sprint · {stats['active_cohorts']} active cohorts · {stats['scorecards_count']} scorecards."
        )
        total_items = len(project_tasks["items"]) if project_tasks and project_tasks.get("items") else 0
        opt1 = (
            f"(Recommended) Work on {top['badge']} {top['title']} — or pick from {total_items} active task(s) (/obsi next / done)"
            if top
            else "(Recommended) Layer 3 — Daily Execution (log progress / next task / weekly plan / done)"
        )
        options = [
            opt1,
            "Layer 1 — 30,000-ft Market Consultant (/obsi-consult)",
            "Layer 2 — Cohort Design & Advisory Priority (/obsi-priority)",
            "Layer 0 — Add Project or Pillar (/obsi-setup)",
            "Layer 4 — In-Flight Transcript & Vault Inspector (/obsi-inspect)",
        ]

    return {
        "state": "ready",
        "workspace_mode": workspace_mode,
        "vault_path": vault_path,
        "detected_project": detected,
        "umbrella_project": None,
        "workspace_projects": ws_entries,
        "unregistered_subfolders": unregistered,
        "stats": stats,
        "project_tasks": project_tasks,
        "project_tasks_card": project_tasks_card,
        "summary_2lines": summary,
        "recommended_options": options,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve 5-layer Hub menu for /obsi.")
    parser.add_argument("--cwd", default=os.getcwd(), help="Current workspace path")
    parser.add_argument("--project", default="", help="Optional explicit project name or alias")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to brain-os.json")
    parser.add_argument("--vault", default="", help="Optional Vault path override")
    parser.add_argument("--max-tasks", type=int, default=5, help="Max active tasks shown per project")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    res = resolve_hub(
        cwd=args.cwd,
        config_path=args.config,
        vault_override=args.vault,
        max_tasks=args.max_tasks,
        explicit_project=args.project,
    )
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(res["summary_2lines"])
        if res.get("project_tasks_card"):
            print()
            print(res["project_tasks_card"])
        print()
        for i, opt in enumerate(res["recommended_options"], 1):
            print(f"  {i}. {opt}")


if __name__ == "__main__":
    main()
