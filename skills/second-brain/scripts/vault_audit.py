#!/usr/bin/env python3
"""
vault_audit.py
Deterministic integrity auditor for Obsidian Second Brain Vault & skills.
Returns structured verified/warnings/errors buckets and non-zero exit on errors.
"""
import argparse
import glob
import json
import os
import re
import sys
import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STALE_PATTERNS = (
    "brain-consult",
    "obsi-architect",
    "obsi-scoper",
    "obsi-prioritizer",
    "obsi-tactical",
    "obsi-inspector",
    "/obsi consult",
    "/obsi scope",
    "/obsi arch",
    "/obsi inspect",
)
MAX_SKILL_BYTES = 3500
FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---", re.DOTALL)
CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
BASE_FENCE_RE = re.compile(r"```base\r?\n(.*?)\r?\n```", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]|#\r\n]+)")
DEFAULT_CONFIG_PATH = os.path.expanduser(os.path.join("~", ".gemini", "config", "brain-os.json"))


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _read_text(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def default_vault_from_config() -> str:
    if os.path.exists(DEFAULT_CONFIG_PATH):
        try:
            cfg = json.loads(_read_text(DEFAULT_CONFIG_PATH))
            if isinstance(cfg, dict) and cfg.get("vault_path"):
                return str(cfg["vault_path"])
        except Exception:
            pass
    return os.path.expanduser(os.path.join("~", "Obsidian", "FounderBrain"))


def parse_frontmatter(txt: str, is_template: bool = False) -> tuple[dict | None, str | None]:
    m = FM_RE.match(txt)
    if not m:
        return None, None
    raw = m.group(1)
    if is_template:
        raw = raw.replace("{{date}}", "2026-01-01").replace("{{title}}", "Template Title").replace("{{pillar}}", "Projects")
    try:
        data = yaml.safe_load(raw) or {}
        if not isinstance(data, dict):
            return None, f"frontmatter is {type(data).__name__}, expected mapping"
        return data, None
    except Exception as exc:
        return None, str(exc)


def check_base_spec(label: str, raw_yaml: str, verified: list[str], errors: list[str]) -> None:
    if re.search(r"[\"']S01[\"']|\bsprint\s*==\s*[\"']S01[\"']", raw_yaml):
        errors.append(f"{label}: hardcodes sprint S01 filter")
    try:
        spec = yaml.safe_load(raw_yaml) or {}
    except Exception as exc:
        errors.append(f"{label}: YAML error in base block: {exc}")
        return
    if not isinstance(spec, dict):
        errors.append(f"{label}: base spec must be a YAML dict")
        return
    missing_null = []
    for view in spec.get("views") or []:
        if isinstance(view, dict) and view.get("type") == "kanban" and "groupOrder" in view:
            go = view.get("groupOrder") or []
            if None not in go:
                missing_null.append(view.get("name", "unnamed"))
    if missing_null:
        errors.append(f"{label}: kanban view(s) missing `null` in groupOrder: {', '.join(missing_null)}")
    else:
        verified.append(f"{label}: valid base spec")


def run_audit(vault_path: str, skills_dir: str) -> dict:
    verified: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []

    if os.path.isdir(skills_dir):
        skill_files = sorted(glob.glob(os.path.join(skills_dir, "*", "SKILL.md")))
        skill_count = 0
        for sp in skill_files:
            skill_count += 1
            folder_name = os.path.basename(os.path.dirname(sp))
            raw_bytes = _read_bytes(sp)
            size = len(raw_bytes)
            txt = raw_bytes.decode("utf-8", errors="replace")
            if size > MAX_SKILL_BYTES:
                errors.append(f"Skill {folder_name}/SKILL.md exceeds {MAX_SKILL_BYTES} B ({size} B)")
            fm, err = parse_frontmatter(txt)
            if err or fm is None:
                errors.append(f"Skill {folder_name}/SKILL.md invalid YAML frontmatter: {err}")
            else:
                if fm.get("name") != folder_name:
                    errors.append(f"Skill {folder_name}/SKILL.md name '{fm.get('name')}' != folder '{folder_name}'")
                if not str(fm.get("description") or "").strip():
                    errors.append(f"Skill {folder_name}/SKILL.md missing description")

        for root, dirs, files in os.walk(skills_dir):
            dirs[:] = [d for d in dirs if d != "_archive"]
            for fn in sorted(files):
                if not fn.endswith(".md"):
                    continue
                fp = os.path.join(root, fn)
                rel = os.path.relpath(fp, skills_dir).replace("\\", "/")
                txt = _read_text(fp)
                for pat in STALE_PATTERNS:
                    if pat in txt:
                        errors.append(f"Skills doc `{rel}` has stale ref `{pat}`")
        verified.append(f"Skills audit checked {skill_count} SKILL.md files under {skills_dir}")
    else:
        warnings.append(f"Skills directory not found: {skills_dir}")

    if not os.path.isdir(vault_path):
        errors.append(f"Vault directory not found: {vault_path}")
        return {"verified": verified, "warnings": warnings, "errors": errors}

    all_md: list[tuple[str, str]] = []
    all_base: list[tuple[str, str]] = []
    for root, dirs, files in os.walk(vault_path):
        dirs[:] = [d for d in dirs if d not in (".git", ".obsidian", ".trash")]
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, vault_path).replace("\\", "/")
            if fn.endswith(".md"):
                all_md.append((rel, fp))
            elif fn.endswith(".base"):
                all_base.append((rel, fp))

    note_stems = {os.path.splitext(os.path.basename(fp))[0] for _, fp in all_md}
    base_names = {os.path.basename(fp) for _, fp in all_base}
    base_stems = {os.path.splitext(b)[0] for b in base_names}
    valid_targets = note_stems | base_names | base_stems

    task_status_by_stem: dict[str, str] = {}
    parsed_tasks: list[tuple[str, dict]] = []
    workspace_owners: dict[str, tuple[str, list[str]]] = {}

    for rel, fp in all_md:
        txt = _read_text(fp)
        is_tpl = rel.startswith("05-Resources/Templates/")
        fm, err = parse_frontmatter(txt, is_template=is_tpl)
        if err:
            errors.append(f"Vault `{rel}` invalid YAML: {err}")
            fm = {}
        fm = fm or {}

        for idx, bmatch in enumerate(BASE_FENCE_RE.finditer(txt), 1):
            check_base_spec(f"{rel}#base-{idx}", bmatch.group(1), verified, errors)

        stripped = CODE_FENCE_RE.sub("", txt)
        for m in WIKILINK_RE.finditer(stripped):
            target = m.group(1).strip()
            if not target or target.startswith("<") or target.startswith("{{"):
                continue
            if "/" in target:
                target_base = target.rsplit("/", 1)[-1]
                if target_base not in valid_targets and target not in valid_targets:
                    errors.append(f"Vault `{rel}` broken wikilink [[{target}]]")
            elif target not in valid_targets:
                errors.append(f"Vault `{rel}` broken wikilink [[{target}]]")

        for pat in STALE_PATTERNS:
            if pat in txt:
                errors.append(f"Vault `{rel}` references stale/archived skill `{pat}`")

        if rel.startswith("01-Projects/"):
            if fm.get("type") != "project":
                errors.append(f"Project `{rel}` missing `type: project`")
            if not str(fm.get("pillar") or "").strip():
                errors.append(f"Project `{rel}` missing `pillar`")
            if "```base" not in txt:
                errors.append(f"Project `{rel}` missing inline ```base board")
            ws_raw = str(fm.get("workspace") or "").strip()
            if ws_raw:
                ws_norm = os.path.normcase(os.path.normpath(os.path.abspath(ws_raw)))
                proj_name = os.path.splitext(os.path.basename(fp))[0]
                if ws_norm not in workspace_owners:
                    workspace_owners[ws_norm] = (ws_raw, [proj_name])
                else:
                    workspace_owners[ws_norm][1].append(proj_name)

        if rel.startswith("02-Tasks/"):
            stem = os.path.splitext(os.path.basename(fp))[0]
            task_status_by_stem[stem] = str(fm.get("status") or "")
            parsed_tasks.append((rel, fm))

    for rel, fp in all_base:
        raw_base = _read_text(fp)
        check_base_spec(rel, raw_base, verified, errors)

    for _, (ws_display, owners) in sorted(workspace_owners.items()):
        if len(owners) > 1:
            warnings.append(
                f"Duplicate workspace path `{ws_display}` shared by: {', '.join(owners)} "
                "(assign dedicated subfolder workspaces or clear duplicate workspace on logical sub-projects)"
            )

    for rel, fm in parsed_tasks:
        status = str(fm.get("status") or "")
        action = str(fm.get("action") or "").strip()
        day = str(fm.get("day") or "").strip()
        today = fm.get("today")
        dep = str(fm.get("depends_on") or "").strip()

        if status in ("Sprint", "Doing") and not action:
            errors.append(f"Active task `{rel}` ({status}) missing `action:`")
        if today is True and status in ("Done", "Locked"):
            errors.append(f"Task `{rel}` has `today: true` while `status: {status}`")

        if status == "Locked":
            if not dep:
                warnings.append(f"Locked task `{rel}` has empty `depends_on`")
            else:
                m = WIKILINK_RE.search(dep)
                blocker = m.group(1).strip() if m else dep
                blocker_status = task_status_by_stem.get(blocker)
                if blocker_status is None:
                    errors.append(f"Orphan Locked task `{rel}` depends on missing `{blocker}`")
                elif blocker_status == "Done":
                    errors.append(f"Unlockable Locked task `{rel}`: blocker `{blocker}` is already Done")

    verified.append(f"Vault audit scanned {len(all_md)} markdown notes, {len(all_base)} .base files, {len(parsed_tasks)} tasks")
    return {"verified": verified, "warnings": warnings, "errors": errors}


def main() -> None:
    default_skills = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    parser = argparse.ArgumentParser(description="Deterministic audit for Second Brain Vault & skills.")
    parser.add_argument("--vault", default="", help="Path to Obsidian Vault (reads brain-os.json by default)")
    parser.add_argument("--skills-dir", default=default_skills, help="Path to skills directory")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args()

    vault = args.vault or default_vault_from_config()
    res = run_audit(vault, args.skills_dir)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print("== VERIFIED ==")
        for v in res["verified"]:
            print(f"  [OK] {v}")
        print("== WARNINGS ==")
        if not res["warnings"]:
            print("  (none)")
        for w in res["warnings"]:
            print(f"  [WARN] {w}")
        print("== ERRORS ==")
        if not res["errors"]:
            print("  (none)")
        for e in res["errors"]:
            print(f"  [ERR] {e}")

    sys.exit(1 if res["errors"] else 0)


if __name__ == "__main__":
    main()
