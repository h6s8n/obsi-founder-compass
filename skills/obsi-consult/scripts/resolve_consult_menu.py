#!/usr/bin/env python3
"""
resolve_consult_menu.py
Zero-Recall Context-Aware Smart Menu resolver for /obsi-consult.
Detects active project from cwd, inspects its Scorecard & Macro Focus Bundles,
classifies workflow state, and outputs ready-to-render options for ask_question.
"""
import argparse
import datetime
import json
import os
import re
import sys
import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_CONFIG_PATH = os.path.expanduser(os.path.join("~", ".gemini", "config", "brain-os.json"))
FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---", re.DOTALL)
BUNDLE_HEAD_RE = re.compile(r"^(?:\d+\.\s+|-\s+)\*\*(.+?)\*\*")
COHORT_READY_RE = re.compile(r"(کورس|Cohort|لایه ۲|ready_for_cohorts)", re.I)


def load_config(config_path: str | None = None) -> dict:
    path = config_path or DEFAULT_CONFIG_PATH
    cfg = {
        "vault_path": os.path.expanduser(os.path.join("~", "Obsidian", "FounderBrain")),
        "scorecards_dir": "00-Focus/Scorecards",
        "language": "en",
    }
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                cfg.update({k: v for k, v in loaded.items() if v not in (None, "")})
        except Exception:
            pass
    return cfg


def parse_frontmatter(txt: str) -> dict:
    m = FM_RE.match(txt)
    if not m:
        return {}
    try:
        data = yaml.safe_load(m.group(1))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def scan_projects(vault_path: str) -> list[dict]:
    projects_dir = os.path.join(vault_path, "01-Projects")
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
            items.append(
                {
                    "name": os.path.splitext(fn)[0],
                    "path": fp,
                    "workspace": str(fm.get("workspace") or "").strip(),
                    "status": str(fm.get("status") or ""),
                    "pillar": str(fm.get("pillar") or ""),
                }
            )
    return items


def detect_project_from_cwd(cwd: str, projects: list[dict]) -> str | None:
    if not cwd:
        return None
    cwd_norm = os.path.normcase(os.path.normpath(os.path.abspath(cwd)))
    best_name = None
    best_len = -1
    for p in projects:
        ws = p.get("workspace") or ""
        if not ws:
            continue
        ws_norm = os.path.normcase(os.path.normpath(os.path.abspath(ws)))
        if cwd_norm == ws_norm or cwd_norm.startswith(ws_norm + os.sep):
            if len(ws_norm) > best_len:
                best_len = len(ws_norm)
                best_name = p["name"]
    if best_name:
        return best_name

    base = os.path.basename(cwd_norm)
    for p in projects:
        if p["name"].lower() == base:
            return p["name"]
    return None


def extract_bundles(scorecard_txt: str) -> list[str]:
    bundles: list[str] = []
    in_section = False
    for line in scorecard_txt.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if "محورهای کلان" in stripped or "Macro Focus Bundles" in stripped:
                in_section = True
                continue
            if in_section:
                break
        if in_section:
            m = BUNDLE_HEAD_RE.match(line)
            if m:
                title = m.group(1).strip().rstrip(":：").strip()
                if title and title != "...":
                    bundles.append(title)
    return bundles


def resolve_menu(
    vault_path: str,
    cwd: str = "",
    explicit_project: str = "",
    scorecards_rel: str = "00-Focus/Scorecards",
    stale_days: int = 30,
    lang: str = "en",
) -> dict:
    is_fa = str(lang).lower() == "fa"
    projects = scan_projects(vault_path)
    scorecards_dir = os.path.join(vault_path, scorecards_rel.replace("/", os.sep))

    for p in projects:
        sc_candidate = os.path.join(scorecards_dir, f"{p['name']}.md")
        p["has_scorecard"] = os.path.exists(sc_candidate)

    detected = explicit_project.strip() or detect_project_from_cwd(cwd, projects)
    if not detected:
        if is_fa:
            proj_opts = [
                f"{p['name']} ({'دارای Scorecard' if p['has_scorecard'] else 'جدید'})"
                for p in projects
            ]
            proj_opts.append("تعریف پروژه جدید")
            summary = "این پوشه مستقیم به هیچ پروژه‌ای در ابسیدین وصل نیست.\nکدام پروژه را بررسی یا راه‌اندازی کنیم؟"
        else:
            proj_opts = [
                f"{p['name']} ({'has Scorecard' if p['has_scorecard'] else 'new'})"
                for p in projects
            ]
            proj_opts.append("Register a new project")
            summary = "Current workspace is not linked to a Vault project yet.\nWhich project should we inspect or launch?"

        return {
            "detected_project": None,
            "state": "pick_project",
            "stage": "",
            "last_full_audit": None,
            "age_days": None,
            "active_deep_dive": "",
            "bundles": [],
            "projects": [{"name": p["name"], "has_scorecard": p["has_scorecard"]} for p in projects],
            "summary_2lines": summary,
            "recommended_options": proj_opts,
        }

    sc_path = os.path.join(scorecards_dir, f"{detected}.md")
    if not os.path.exists(sc_path):
        if is_fa:
            summary = (
                f"پروژه «{detected}» از ورک‌اسپیس شناسایی شد، ولی هنوز Scorecard ندارد.\n"
                "گام اول: با چند سوال سریع و «آینه ویژن» تصویر کلان را می‌بندیم."
            )
            opts = ["(Recommended) شروع ارزیابی کلان و آینه ویژن از صفر", "تغییر به پروژه دیگر"]
        else:
            summary = (
                f"Detected workspace project '{detected}' — no Macro Scorecard yet.\n"
                "Step 1: align on your Vision Mirror before mapping market gaps."
            )
            opts = ["(Recommended) Start Vision Mirror & full market audit", "Switch to another project"]

        return {
            "detected_project": detected,
            "state": "new",
            "stage": "",
            "last_full_audit": None,
            "age_days": None,
            "active_deep_dive": "",
            "bundles": [],
            "projects": [{"name": p["name"], "has_scorecard": p["has_scorecard"]} for p in projects],
            "summary_2lines": summary,
            "recommended_options": opts,
        }

    with open(sc_path, "r", encoding="utf-8", errors="replace") as f:
        sc_txt = f.read()
    fm = parse_frontmatter(sc_txt)
    stage = str(fm.get("stage") or "")
    lv_raw = fm.get("last_full_audit") or fm.get("updated")
    lv_str = lv_raw.isoformat() if isinstance(lv_raw, datetime.date) else str(lv_raw or "")
    age_days: int | None = None
    if lv_str:
        try:
            age_days = (datetime.date.today() - datetime.date.fromisoformat(lv_str[:10])).days
        except ValueError:
            age_days = None

    active_deep_dive = str(fm.get("active_deep_dive") or "")
    bundles = extract_bundles(sc_txt)

    if age_days is not None and age_days > stale_days:
        state = "stale"
    elif bundles and (not active_deep_dive or COHORT_READY_RE.search(active_deep_dive)):
        state = "ready_for_cohorts"
    else:
        state = "in_progress"

    if is_fa:
        if state == "stale":
            summary = f"پروژه «{detected}» — آخرین ارزیابی {age_days} روز پیش ({lv_str}) بوده است.\nوضعیت فعلی: {active_deep_dive or stage or 'آماده بازبینی'}"
            options = [f"(Recommended) بازبینی سریع تابلوی {detected}", "ادامه مستقیم بدون ارزیابی مجدد"]
        elif state == "ready_for_cohorts":
            summary = f"پروژه «{detected}» — لایه کلان و {len(bundles)} محور اصلی ثبت شده‌اند.\nوضعیت فعلی: {active_deep_dive or 'آماده انتخاب کورس‌ها (/obsi-priority)'}"
            options = ["(Recommended) رفتن به مرحله بعد: انتخاب کورس‌ها (/obsi-priority)"]
        else:
            summary = f"پروژه «{detected}» — روی کارنامه در حال کار هستیم.\nنقطه توقف: {active_deep_dive or stage or 'ادامه گفتگو'}"
            options = ["(Recommended) ادامه مستقیم از آخرین نقطه توقف"]
        for idx, b in enumerate(bundles, 1):
            options.append(f"عمیق‌شدن روی محور {idx}: {b}")
        options.append(f"شروع مجدد ارزیابی کلان «{detected}» از اول")
        options.append("تغییر به پروژه دیگر")
    else:
        if state == "stale":
            summary = f"Project '{detected}' — last full audit was {age_days}d ago ({lv_str}).\nCurrent focus: {active_deep_dive or stage or 'Ready for refresh'}"
            options = [f"(Recommended) Refresh Scorecard for '{detected}'", "Resume directly without refreshing"]
        elif state == "ready_for_cohorts":
            summary = f"Project '{detected}' — Vision & {len(bundles)} Macro Focus Bundles are locked.\nCurrent stage: {active_deep_dive or 'Ready for Cohort design (/obsi-priority)'}"
            options = ["(Recommended) Move to Layer 2: Cohort design & priority (/obsi-priority)"]
        else:
            summary = f"Project '{detected}' — Scorecard session in progress.\nStop point: {active_deep_dive or stage or 'Resume consult'}"
            options = ["(Recommended) Resume directly from current stop point"]
        for idx, b in enumerate(bundles, 1):
            options.append(f"Deep-dive Bundle {idx}: {b}")
        options.append(f"Restart full market audit for '{detected}'")
        options.append("Switch to another project")

    return {
        "detected_project": detected,
        "state": state,
        "stage": stage,
        "last_full_audit": lv_str or None,
        "age_days": age_days,
        "active_deep_dive": active_deep_dive,
        "bundles": bundles,
        "scorecard_path": sc_path,
        "projects": [{"name": p["name"], "has_scorecard": p["has_scorecard"]} for p in projects],
        "summary_2lines": summary,
        "recommended_options": options,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve /obsi-consult smart entry menu.")
    parser.add_argument("--cwd", default=os.getcwd(), help="Current workspace directory")
    parser.add_argument("--project", default="", help="Optional explicit project name")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to brain-os.json")
    parser.add_argument("--vault", default="", help="Override Vault path")
    parser.add_argument("--lang", default="", help="Override language ('en' or 'fa')")
    parser.add_argument("--stale-days", type=int, default=30, help="Days before Scorecard counts stale")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    cfg = load_config(args.config)
    vault = args.vault or cfg["vault_path"]
    lang = args.lang or cfg.get("language", "en")
    res = resolve_menu(
        vault,
        cwd=args.cwd,
        explicit_project=args.project,
        scorecards_rel=cfg.get("scorecards_dir", "00-Focus/Scorecards"),
        stale_days=args.stale_days,
        lang=lang,
    )
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(res["summary_2lines"])
        for i, opt in enumerate(res["recommended_options"], 1):
            print(f"  {i}. {opt}")


if __name__ == "__main__":
    main()
