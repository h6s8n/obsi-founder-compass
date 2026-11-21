#!/usr/bin/env python3
"""
resolve_consult_menu.py
Zero-Recall Context-Aware Smart Menu resolver for /obsi-consult.
Detects active project(s) from cwd (supporting monorepos, unregistered subfolders,
and bilingual aliases), inspects Scorecard & Macro Focus Bundles, classifies
workflow state, and outputs ready-to-render options for ask_question.
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
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
BUNDLE_HEAD_RE = re.compile(r"^(?:\d+\.\s+|-\s+)\*\*(.+?)\*\*")
COHORT_READY_RE = re.compile(r"(کورس|Cohort|لایه ۲|ready_for_cohorts)", re.I)
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
                    "cohort": _extract_link_stem(fm.get("cohort")),
                    "status": str(fm.get("status") or ""),
                    "pillar": str(fm.get("pillar") or ""),
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


def detect_project_from_cwd(cwd: str, projects: list[dict]) -> str | None:
    single, _, _ = detect_workspace_projects(projects, cwd)
    return single["name"] if single else None


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
    projects = scan_projects(vault_path, scorecards_rel=scorecards_rel)
    scorecards_dir = os.path.join(vault_path, scorecards_rel.replace("/", os.sep))
    unregistered = discover_unregistered_subfolders(cwd, projects)

    detected: str | None = None
    matched: list[dict] = []
    umbrella_name: str | None = None

    if explicit_project.strip():
        resolved = resolve_project_query(explicit_project.strip(), projects)
        detected = resolved["name"] if resolved else explicit_project.strip()
        matched = [resolved] if resolved else []
    else:
        single, matched, umbrella_name = detect_workspace_projects(projects, cwd)
        detected = single["name"] if single else None

    if not detected and len(matched) > 1:
        ws_entries = [
            {
                "name": p["name"],
                "workspace": p["workspace"],
                "parent": p["parent"],
                "aliases": p["aliases"],
                "pillar": p["pillar"],
                "has_scorecard": p["has_scorecard"],
                "is_umbrella": bool(umbrella_name and p["name"].lower() == umbrella_name.lower()),
            }
            for p in matched
        ]
        ws_entries.sort(key=lambda x: (1 if x["is_umbrella"] else 0, x["name"].lower()))
        unreg_count = len(unregistered)
        if is_fa:
            unreg_part = f" (و {unreg_count} پوشه ثبت‌نشده)" if unreg_count else ""
            summary = (
                f"این ورک‌اسپیس شامل {len(matched)} پروژه ثبت‌شده است{unreg_part}.\n"
                "کدام پروژه را برای مشاوره کلان انتخاب می‌کنی؟"
            )
            proj_opts = []
            for entry in ws_entries:
                tag = "کل مجموعه · " if entry["is_umbrella"] else ""
                sc_label = "دارای Scorecard" if entry["has_scorecard"] else "جدید"
                proj_opts.append(f"{entry['name']} ({tag}{sc_label})")
            if unreg_count:
                proj_opts.append("➕ ثبت پوشه دیگر از همین ورک‌اسپیس به عنوان پروژه جدا (/obsi-setup)")
            proj_opts.append("سایر پروژه‌های ابسیدین / تعریف پروژه جدید")
        else:
            unreg_part = f" (and {unreg_count} unregistered subfolder(s))" if unreg_count else ""
            summary = (
                f"This workspace contains {len(matched)} registered projects{unreg_part}.\n"
                "Which project should we review in 30,000-ft consultation?"
            )
            proj_opts = []
            for entry in ws_entries:
                tag = "umbrella · " if entry["is_umbrella"] else ""
                sc_label = "has Scorecard" if entry["has_scorecard"] else "new"
                proj_opts.append(f"{entry['name']} ({tag}{sc_label})")
            if unreg_count:
                proj_opts.append("➕ Register another subfolder from this workspace as a separate project (/obsi-setup)")
            proj_opts.append("Other Vault projects / Register new project")

        return {
            "detected_project": None,
            "state": "pick_project",
            "workspace_mode": "multi_project",
            "umbrella_project": umbrella_name,
            "workspace_projects": ws_entries,
            "unregistered_subfolders": unregistered,
            "stage": "",
            "last_full_audit": None,
            "age_days": None,
            "active_deep_dive": "",
            "bundles": [],
            "projects": [{"name": p["name"], "has_scorecard": p["has_scorecard"]} for p in projects],
            "summary_2lines": summary,
            "recommended_options": proj_opts,
        }

    if not detected:
        if is_fa:
            proj_opts = [
                f"{p['name']} ({'دارای Scorecard' if p['has_scorecard'] else 'جدید'})"
                for p in projects
            ]
            if unregistered:
                proj_opts.append("➕ ثبت پوشه دیگر از همین ورک‌اسپیس به عنوان پروژه جدا (/obsi-setup)")
            proj_opts.append("تعریف پروژه جدید")
            summary = "این پوشه مستقیم به هیچ پروژه‌ای در ابسیدین وصل نیست.\nکدام پروژه را بررسی یا راه‌اندازی کنیم؟"
        else:
            proj_opts = [
                f"{p['name']} ({'has Scorecard' if p['has_scorecard'] else 'new'})"
                for p in projects
            ]
            if unregistered:
                proj_opts.append("➕ Register another subfolder from this workspace as a separate project (/obsi-setup)")
            proj_opts.append("Register a new project")
            summary = "Current workspace is not linked to a Vault project yet.\nWhich project should we inspect or launch?"

        return {
            "detected_project": None,
            "state": "pick_project",
            "workspace_mode": "unmatched",
            "umbrella_project": None,
            "workspace_projects": [],
            "unregistered_subfolders": unregistered,
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
                f"پروژه «{detected}» شناسایی شد، ولی هنوز Scorecard ندارد.\n"
                "گام اول: با چند سوال سریع و «آینه ویژن» تصویر کلان را می‌بندیم."
            )
            opts = ["(Recommended) شروع ارزیابی کلان و آینه ویژن از صفر", "تغییر به پروژه دیگر"]
        else:
            summary = (
                f"Detected project '{detected}' — no Macro Scorecard yet.\n"
                "Step 1: align on your Vision Mirror before mapping market gaps."
            )
            opts = ["(Recommended) Start Vision Mirror & full market audit", "Switch to another project"]

        return {
            "detected_project": detected,
            "state": "new",
            "workspace_mode": "single_project",
            "unregistered_subfolders": unregistered,
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
        "workspace_mode": "single_project",
        "unregistered_subfolders": unregistered,
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
    parser.add_argument("--project", default="", help="Optional explicit project name or alias")
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
