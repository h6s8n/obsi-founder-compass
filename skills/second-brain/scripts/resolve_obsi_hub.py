#!/usr/bin/env python3
"""
resolve_obsi_hub.py
Thin Hub resolver for /obsi: checks brain-os.json & Vault presence,
detects active project from cwd, summarizes live stats, and returns
ready-to-render 5-layer Hub options for ask_question.
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


def detect_project(vault_path: str, cwd: str) -> tuple[str | None, int]:
    projects_dir = os.path.join(vault_path, "01-Projects")
    projects: list[tuple[str, str]] = []
    if os.path.isdir(projects_dir):
        for root, _, files in os.walk(projects_dir):
            for fn in sorted(files):
                if not fn.endswith(".md"):
                    continue
                fp = os.path.join(root, fn)
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    fm = parse_frontmatter(f.read())
                if fm.get("type") == "project":
                    projects.append((os.path.splitext(fn)[0], str(fm.get("workspace") or "").strip()))

    if not cwd or not projects:
        return None, len(projects)

    cwd_norm = os.path.normcase(os.path.normpath(os.path.abspath(cwd)))
    best_name = None
    best_len = -1
    for name, ws in projects:
        if not ws:
            continue
        ws_norm = os.path.normcase(os.path.normpath(os.path.abspath(ws)))
        if cwd_norm == ws_norm or cwd_norm.startswith(ws_norm + os.sep):
            if len(ws_norm) > best_len:
                best_len = len(ws_norm)
                best_name = name
    if best_name:
        return best_name, len(projects)

    base = os.path.basename(cwd_norm)
    for name, _ in projects:
        if name.lower() == base:
            return name, len(projects)
    return None, len(projects)


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


def resolve_hub(cwd: str = "", config_path: str | None = None, vault_override: str = "") -> dict:
    cfg, cfg_exists = load_config(config_path)
    vault_path = vault_override or str(cfg.get("vault_path") or "")
    lang = str(cfg.get("language") or "en").lower()
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
            "vault_path": vault_path or None,
            "detected_project": None,
            "stats": {},
            "summary_2lines": summary,
            "recommended_options": opts,
        }

    detected, proj_count = detect_project(vault_path, cwd)
    stats = count_vault_stats(vault_path)
    stats["projects_count"] = proj_count

    if lang == "fa":
        proj_label = f"پروژه فعال: «{detected}»" if detected else f"{proj_count} پروژه در ابسیدین"
        summary = (
            f"مغز دوم آماده است ({proj_label}).\n"
            f"آمار زنده: {stats['today_tasks']} تسک امروز · {stats['sprint_tasks']} تسک اسپرینت · {stats['active_cohorts']} کورس فعال · {stats['scorecards_count']} کارنامه."
        )
        options = [
            "(Recommended) لایه ۳ — اجرای روزمره (کار بعدی / برنامه هفته / ثبت سریع / بستن تسک)",
            "لایه ۱ — مشاور کلان بازار پروژه (/obsi-consult)",
            "لایه ۲ — انتخاب کورس‌ها و اولویت‌بندی (/obsi-priority)",
            "لایه ۰ — افزودن پروژه یا ستون جدید (/obsi-setup)",
            "لایه ۴ — بازرس چت و سلامت ابسیدین (/obsi-inspect)",
        ]
    else:
        proj_label = f"Active project: {detected}" if detected else f"{proj_count} project(s) in Vault"
        summary = (
            f"Second Brain is ready ({proj_label}).\n"
            f"Live stats: {stats['today_tasks']} today · {stats['sprint_tasks']} sprint · {stats['active_cohorts']} active cohorts · {stats['scorecards_count']} scorecards."
        )
        options = [
            "(Recommended) Layer 3 — Daily Execution (next task / weekly plan / capture / done)",
            "Layer 1 — 30,000-ft Market Consultant (/obsi-consult)",
            "Layer 2 — Cohort Design & Advisory Priority (/obsi-priority)",
            "Layer 0 — Add Project or Pillar (/obsi-setup)",
            "Layer 4 — In-Flight Transcript & Vault Inspector (/obsi-inspect)",
        ]

    return {
        "state": "ready",
        "vault_path": vault_path,
        "detected_project": detected,
        "stats": stats,
        "summary_2lines": summary,
        "recommended_options": options,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve 5-layer Hub menu for /obsi.")
    parser.add_argument("--cwd", default=os.getcwd(), help="Current workspace path")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to brain-os.json")
    parser.add_argument("--vault", default="", help="Optional Vault path override")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    res = resolve_hub(cwd=args.cwd, config_path=args.config, vault_override=args.vault)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(res["summary_2lines"])
        for i, opt in enumerate(res["recommended_options"], 1):
            print(f"  {i}. {opt}")


if __name__ == "__main__":
    main()
