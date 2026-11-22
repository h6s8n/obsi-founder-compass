#!/usr/bin/env python3
"""
vault_engine.py
Zero-hardcode, spec-driven query & mutation engine for Obsidian Native Bases Vaults.
Reads live Markdown frontmatter and parses *.base YAML views/filters dynamically.
"""
from __future__ import annotations

import datetime
import os
import posixpath
import re
import sys
from pathlib import Path
from typing import Any
import yaml

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_HUB_SCRIPTS_DIR = os.path.abspath(os.path.join(_THIS_DIR, "..", "skills", "second-brain", "scripts"))
if _HUB_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _HUB_SCRIPTS_DIR)

import resolve_obsi_hub as roh  # noqa: E402

FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---(?=\r?\n|$)", re.DOTALL)
H1_RE = re.compile(r"^\s*#\s+(.+?)\s*$")
INFOLDER_RE = re.compile(r'^file\.inFolder\(\s*(["\'])(.*?)\1\s*\)$')
CONTAINS_RE = re.compile(r'^([a-zA-Z0-9_.\-]+)\.contains\(\s*(["\'])(.*?)\2\s*\)$')
BIN_CMP_RE = re.compile(r'^([a-zA-Z0-9_.\-]+)\s*(==|!=|>=|<=|>|<)\s*(.+)$')
NUM_RE = re.compile(r"^-?\d+(?:\.\d+)?$")

SKIP_VAULT_DIRS = {
    ".git",
    ".obsidian",
    ".trash",
    "99-Archive",
    "node_modules",
    "__pycache__",
}

PRIORITY_RANK = {"high": 0, "medium": 1, "normal": 1, "low": 2}
DEFAULT_STATUS_FALLBACK = ["doing", "sprint", "backlog", "todo", "locked", "done"]


def _as_file_uri(abs_path: str) -> str:
    return Path(os.path.abspath(abs_path)).as_uri()


def _strip_quotes(raw: str) -> str:
    txt = raw.strip()
    if len(txt) >= 2 and txt[0] == txt[-1] and txt[0] in ('"', "'"):
        return txt[1:-1]
    return txt


def _parse_literal(raw: str) -> Any:
    txt = raw.strip()
    if (len(txt) >= 2 and txt[0] == txt[-1] and txt[0] in ('"', "'")):
        return txt[1:-1]
    low = txt.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("null", "none", "~"):
        return None
    if NUM_RE.match(txt):
        return float(txt) if "." in txt else int(txt)
    return txt


def _norm_scalar(val: Any) -> Any:
    if isinstance(val, bool) or val is None:
        return val
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.isoformat()
    if isinstance(val, str):
        return roh._extract_link_stem(val)
    return str(val)


def load_vault_context(config_path: str | None = None, vault_override: str = "") -> dict[str, Any]:
    """Resolve active Vault path and configuration without hardcoding local paths."""
    resolved_cfg_path = config_path or os.environ.get("OBSI_CONFIG_PATH") or roh.DEFAULT_CONFIG_PATH
    cfg, cfg_exists = roh.load_config(resolved_cfg_path)
    env_vault = os.environ.get("OBSI_VAULT_PATH", "").strip()
    vault_path = (vault_override or env_vault or str(cfg.get("vault_path") or "")).strip()
    if vault_path:
        vault_path = os.path.abspath(os.path.expanduser(vault_path))
    lang = str(cfg.get("language") or "en").strip().lower() or "en"
    configured = bool(vault_path and os.path.isdir(vault_path))
    return {
        "configured": configured,
        "config_exists": cfg_exists,
        "config_path": resolved_cfg_path,
        "vault_path": vault_path,
        "language": lang,
        "config": cfg,
    }


def _require_vault(vault_path: str) -> str:
    if not vault_path or not os.path.isdir(vault_path):
        raise ValueError(
            "Obsidian Vault is not configured or directory does not exist. "
            "Run /obsi-setup first or set ~/.gemini/config/brain-os.json."
        )
    return os.path.abspath(vault_path)


def parse_note(abs_path: str, vault_path: str) -> dict[str, Any]:
    """Parse Markdown frontmatter and basic metadata from a Vault note."""
    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    fm: dict[str, Any] = {}
    body = text
    m = FM_RE.match(text)
    if m:
        body = text[m.end():]
        try:
            loaded = yaml.safe_load(m.group(1))
            if isinstance(loaded, dict):
                fm = loaded
        except Exception:
            fm = {}

    file_name = os.path.splitext(os.path.basename(abs_path))[0]
    rel_path = os.path.relpath(abs_path, vault_path).replace("\\", "/")
    rel_dir = posixpath.dirname(rel_path)

    heading = ""
    for line in body.splitlines():
        hm = H1_RE.match(line)
        if hm:
            heading = hm.group(1).strip()
            break

    title = str(fm.get("title") or heading or file_name).strip()
    return {
        "file_name": file_name,
        "title": title,
        "rel_path": rel_path,
        "rel_dir": "" if rel_dir == "." else rel_dir,
        "abs_path": os.path.abspath(abs_path),
        "file_uri": _as_file_uri(abs_path),
        "fm": fm,
    }


def _scan_notes(vault_path: str, subfolder: str | None = None) -> list[dict[str, Any]]:
    root_dir = os.path.join(vault_path, subfolder.replace("/", os.sep)) if subfolder else vault_path
    if not os.path.isdir(root_dir):
        return []
    notes: list[dict[str, Any]] = []
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in sorted(dirs) if d not in SKIP_VAULT_DIRS]
        for fn in sorted(files):
            if not fn.endswith(".md"):
                continue
            notes.append(parse_note(os.path.join(root, fn), vault_path))
    return notes


def discover_bases(vault_path: str) -> list[dict[str, Any]]:
    """Discover and parse all Obsidian *.base files in the Vault dynamically."""
    vault_abs = _require_vault(vault_path)
    bases: list[dict[str, Any]] = []
    for root, dirs, files in os.walk(vault_abs):
        dirs[:] = [d for d in sorted(dirs) if d not in SKIP_VAULT_DIRS]
        for fn in sorted(files):
            if not fn.endswith(".base"):
                continue
            fp = os.path.join(root, fn)
            rel_path = os.path.relpath(fp, vault_abs).replace("\\", "/")
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    spec = yaml.safe_load(f.read()) or {}
            except Exception as exc:
                bases.append(
                    {
                        "name": os.path.splitext(fn)[0],
                        "rel_path": rel_path,
                        "abs_path": os.path.abspath(fp),
                        "file_uri": _as_file_uri(fp),
                        "filters": None,
                        "properties": {},
                        "views": [],
                        "parse_error": str(exc),
                    }
                )
                continue

            if not isinstance(spec, dict):
                spec = {}

            raw_props = spec.get("properties") if isinstance(spec.get("properties"), dict) else {}
            prop_labels: dict[str, str] = {}
            for k, v in raw_props.items():
                if isinstance(v, dict) and v.get("displayName") is not None:
                    prop_labels[str(k)] = str(v["displayName"])
                else:
                    prop_labels[str(k)] = str(k)

            views: list[dict[str, Any]] = []
            for v in spec.get("views") or []:
                if not isinstance(v, dict):
                    continue
                views.append(
                    {
                        "name": str(v.get("name") or "Default"),
                        "type": str(v.get("type") or "table"),
                        "filters": v.get("filters"),
                        "groupBy": v.get("groupBy"),
                        "groupOrder": v.get("groupOrder"),
                        "order": [str(col) for col in (v.get("order") or [])],
                        "sort": v.get("sort") or [],
                    }
                )

            bases.append(
                {
                    "name": os.path.splitext(fn)[0],
                    "rel_path": rel_path,
                    "abs_path": os.path.abspath(fp),
                    "file_uri": _as_file_uri(fp),
                    "filters": spec.get("filters"),
                    "properties": prop_labels,
                    "views": views,
                }
            )
    bases.sort(key=lambda b: (b["rel_path"].count("/"), b["rel_path"].lower()))
    return bases


def list_bases_summary(vault_path: str) -> dict[str, Any]:
    """Return a clean summary catalog of all discovered *.base files and their views."""
    bases = discover_bases(vault_path)
    out = []
    for b in bases:
        out.append(
            {
                "name": b["name"],
                "rel_path": b["rel_path"],
                "file_uri": b["file_uri"],
                "properties": b["properties"],
                "views": [
                    {
                        "name": v["name"],
                        "type": v["type"],
                        "groupBy": v.get("groupBy"),
                        "columns": v.get("order") or [],
                    }
                    for v in b["views"]
                ],
            }
        )
    return {"vault_path": os.path.abspath(vault_path), "count": len(out), "bases": out}


def extract_folder_hint(filters: Any) -> str | None:
    """Find top-level file.inFolder(...) subfolder hint to avoid unnecessary directory walks."""
    hints: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, str):
            m = INFOLDER_RE.match(node.strip())
            if m:
                folder = m.group(2).strip().strip("/")
                if folder:
                    hints.append(folder)
        elif isinstance(node, dict) and "and" in node:
            for child in node.get("and") or []:
                _walk(child)
        elif isinstance(node, list):
            for child in node:
                _walk(child)

    _walk(filters)
    if not hints:
        return None
    return max(hints, key=len)


def _resolve_note_field(field: str, note: dict[str, Any]) -> Any:
    if field == "file.name":
        return note["file_name"]
    if field == "file.path":
        return note["rel_path"]
    if field == "file.folder":
        return note["rel_dir"]
    return note["fm"].get(field)


def _compare_values(left: Any, op: str, right: Any) -> bool:
    if isinstance(left, list):
        if op == "==":
            return any(_compare_values(el, "==", right) for el in left)
        if op == "!=":
            return all(_compare_values(el, "!=", right) for el in left)

    l_norm = _norm_scalar(left)
    r_norm = _norm_scalar(right)

    if r_norm is None:
        is_empty = l_norm is None or (isinstance(l_norm, str) and l_norm.strip() == "")
        if op == "==":
            return is_empty
        if op == "!=":
            return not is_empty
        return False

    if l_norm is None:
        return op == "!="

    if isinstance(r_norm, bool):
        l_bool = l_norm if isinstance(l_norm, bool) else str(l_norm).strip().lower() == "true"
        if op == "==":
            return l_bool is r_norm
        if op == "!=":
            return l_bool is not r_norm
        return False

    if isinstance(l_norm, (int, float)) and not isinstance(l_norm, bool) and isinstance(r_norm, (int, float)) and not isinstance(r_norm, bool):
        if op == "==":
            return l_norm == r_norm
        if op == "!=":
            return l_norm != r_norm
        if op == ">":
            return l_norm > r_norm
        if op == ">=":
            return l_norm >= r_norm
        if op == "<":
            return l_norm < r_norm
        if op == "<=":
            return l_norm <= r_norm

    l_str = str(l_norm).strip()
    r_str = str(r_norm).strip()
    l_low = l_str.lower()
    r_low = r_str.lower()

    if op == "==":
        return l_low == r_low
    if op == "!=":
        return l_low != r_low
    if op == ">":
        return l_str > r_str
    if op == ">=":
        return l_str >= r_str
    if op == "<":
        return l_str < r_str
    if op == "<=":
        return l_str <= r_str
    return False


def evaluate_filter_node(node: Any, note: dict[str, Any]) -> bool:
    """Evaluate Obsidian Base YAML filter AST against a parsed Markdown note."""
    if node is None:
        return True
    if isinstance(node, list):
        return all(evaluate_filter_node(child, note) for child in node)
    if isinstance(node, dict):
        if "and" in node:
            return all(evaluate_filter_node(c, note) for c in (node.get("and") or []))
        if "or" in node:
            children = node.get("or") or []
            return any(evaluate_filter_node(c, note) for c in children) if children else True
        if "not" in node:
            inner = node.get("not")
            if isinstance(inner, list):
                return not any(evaluate_filter_node(c, note) for c in inner)
            return not evaluate_filter_node(inner, note)
        return True
    if isinstance(node, str):
        expr = node.strip()
        if not expr:
            return True

        fm = INFOLDER_RE.match(expr)
        if fm:
            target = fm.group(2).strip().strip("/").lower()
            if not target:
                return True
            note_dir = note["rel_dir"].strip("/").lower()
            return note_dir == target or note_dir.startswith(target + "/")

        cm = CONTAINS_RE.match(expr)
        if cm:
            field, _, sub = cm.groups()
            val = _resolve_note_field(field, note)
            sub_low = sub.lower()
            if isinstance(val, list):
                return any(sub_low in str(_norm_scalar(x) or "").lower() for x in val)
            return sub_low in str(_norm_scalar(val) or "").lower()

        bm = BIN_CMP_RE.match(expr)
        if bm:
            field, op, raw_rhs = bm.groups()
            lhs = _resolve_note_field(field, note)
            rhs = _parse_literal(raw_rhs)
            return _compare_values(lhs, op, rhs)

        # Bare boolean property expression like `today` or `!archived`
        if expr.startswith("!"):
            return not bool(_resolve_note_field(expr[1:].strip(), note))
        return bool(_resolve_note_field(expr, note))

    return True


def _resolve_project_targets(vault_path: str, project_query: str) -> set[str]:
    q = str(project_query or "").strip()
    if not q:
        return set()
    projects = roh.scan_projects(vault_path)
    resolved = roh.resolve_project_query(q, projects)
    targets = {q.lower()}
    if resolved:
        p_name = resolved["name"]
        targets.add(p_name.lower())
        for child in projects:
            if str(child.get("parent") or "").strip().lower() == p_name.lower():
                targets.add(child["name"].lower())
    return targets


def _note_project_stem(note: dict[str, Any]) -> str:
    raw = str(note["fm"].get("project") or "").strip()
    parts = note["rel_dir"].split("/")
    if raw:
        stem = roh._extract_link_stem(raw)
        if stem.lower().endswith(" moc") and len(parts) >= 2 and parts[0].lower() == "02-tasks":
            return parts[-1]
        return stem
    if len(parts) >= 2 and parts[0].lower() == "02-tasks":
        return parts[-1]
    return ""


def _matches_project(note: dict[str, Any], targets: set[str]) -> bool:
    if not targets:
        return True
    stem = _note_project_stem(note).lower()
    if stem and stem in targets:
        return True
    dir_parts = {p.lower() for p in note["rel_dir"].split("/") if p}
    return bool(dir_parts & targets)


def _priority_rank(val: Any) -> int:
    return PRIORITY_RANK.get(str(val or "").strip().lower(), 3)


def _format_note_row(note: dict[str, Any], columns: list[str] | None = None) -> dict[str, Any]:
    fm = note["fm"]
    status = str(fm.get("status") or "").strip()
    priority = str(fm.get("priority") or "").strip()
    pillar = str(fm.get("pillar") or "").strip()
    project = _note_project_stem(note)
    action = " ".join(str(fm.get("action") or "").split())
    depends_on = roh._extract_link_stem(fm.get("depends_on"))
    row: dict[str, Any] = {
        "file_name": note["file_name"],
        "title": note["title"],
        "project": project,
        "pillar": pillar,
        "status": status,
        "priority": priority,
        "today": fm.get("today") is True,
        "day": str(fm.get("day") or "").strip(),
        "cadence": str(fm.get("cadence") or "").strip(),
        "action": action,
        "depends_on": depends_on,
        "rel_path": note["rel_path"],
        "file_uri": note["file_uri"],
    }
    if columns:
        extras: dict[str, Any] = {}
        for col in columns:
            if col in ("file.name", "file.path", "file.folder") or col in row:
                continue
            val = fm.get(col)
            if val is not None:
                extras[col] = _norm_scalar(val)
        if extras:
            row["extra"] = extras
    return row


def _sort_key_for_view(note: dict[str, Any], view: dict[str, Any] | None) -> tuple:
    fm = note["fm"]
    parts: list[Any] = []

    if view:
        gb = view.get("groupBy")
        gb_prop = ""
        gb_desc = False
        if isinstance(gb, dict):
            gb_prop = str(gb.get("property") or "").strip()
            gb_desc = str(gb.get("direction") or "ASC").upper() == "DESC"
        elif isinstance(gb, str):
            gb_prop = gb.strip()

        if gb_prop:
            raw_val = _resolve_note_field(gb_prop, note)
            val_norm = _norm_scalar(raw_val)
            val_str = "" if val_norm is None else str(val_norm).strip()
            group_order = view.get("groupOrder")
            if isinstance(group_order, list) and group_order:
                order_map: dict[str | None, int] = {}
                for idx, entry in enumerate(group_order):
                    if entry is None or str(entry).strip() == "":
                        order_map.setdefault(None, idx)
                    else:
                        order_map.setdefault(str(entry).strip().lower(), idx)
                lookup = None if val_str == "" else val_str.lower()
                default_idx = order_map.get(None, len(group_order))
                parts.append(order_map.get(lookup, default_idx))
            else:
                parts.append((1 if val_str == "" else 0, val_str.lower()))
                if gb_desc:
                    parts[-1] = (1 if val_str == "" else 0, "".join(chr(255 - min(255, ord(c))) for c in val_str.lower()))

        for s in view.get("sort") or []:
            if not isinstance(s, dict):
                continue
            s_prop = str(s.get("property") or "").strip()
            if not s_prop:
                continue
            s_desc = str(s.get("direction") or "ASC").upper() == "DESC"
            raw_sv = _norm_scalar(_resolve_note_field(s_prop, note))
            sv_str = "" if raw_sv is None else str(raw_sv).strip().lower()
            parts.append((1 if sv_str == "" else 0, sv_str if not s_desc else tuple(-ord(c) for c in sv_str)))

    parts.append(0 if fm.get("today") is True else 1)
    parts.append(_priority_rank(fm.get("priority")))
    parts.append(note["file_name"].lower())
    return tuple(parts)


def _group_label(note: dict[str, Any], view: dict[str, Any] | None) -> str | None:
    if not view or not view.get("groupBy"):
        return None
    gb = view["groupBy"]
    prop = str(gb.get("property") if isinstance(gb, dict) else gb).strip()
    if not prop:
        return None
    val = _norm_scalar(_resolve_note_field(prop, note))
    txt = "" if val is None else str(val).strip()
    return txt if txt else "Uncategorized"


def query_base(
    vault_path: str,
    base: str = "",
    view: str = "",
    project: str = "",
    pillar: str = "",
    status: str = "",
    today: bool | None = None,
    cadence: str = "",
    search: str = "",
    include_done: bool | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    """Query any Obsidian *.base file using its own live YAML filters, grouping, and sorting."""
    vault_abs = _require_vault(vault_path)
    bases = discover_bases(vault_abs)
    if not bases:
        raise ValueError("No *.base files found in Vault.")

    target_base = None
    if base.strip():
        q = base.strip().replace("\\", "/").lower()
        q_stem = q[:-5] if q.endswith(".base") else q
        for b in bases:
            if b["rel_path"].lower() == q or b["name"].lower() == q_stem:
                target_base = b
                break
        if not target_base:
            available = ", ".join(b["rel_path"] for b in bases)
            raise ValueError(f"Base '{base}' not found. Available: {available}")
    else:
        for b in bases:
            if b["name"].lower() == "tasks":
                target_base = b
                break
        if not target_base:
            target_base = bases[0]

    selected_view: dict[str, Any] | None = None
    views = target_base.get("views") or []
    vq = view.strip()
    if vq and vq not in ("*", "all"):
        vq_low = vq.lower()
        for v in views:
            if v["name"].lower() == vq_low:
                selected_view = v
                break
        if not selected_view:
            for v in views:
                if vq_low in v["name"].lower():
                    selected_view = v
                    break
        if not selected_view:
            avail_v = ", ".join(v["name"] for v in views) or "(none)"
            raise ValueError(f"View '{view}' not found in {target_base['rel_path']}. Available: {avail_v}")
    elif not vq and views:
        selected_view = views[0]

    folder_hint = extract_folder_hint(target_base.get("filters"))
    notes = _scan_notes(vault_abs, subfolder=folder_hint)

    proj_targets = _resolve_project_targets(vault_abs, project) if project.strip() else set()
    pillar_low = pillar.strip().lower()
    status_low = status.strip().lower()
    cadence_low = cadence.strip().lower()
    search_low = search.strip().lower()

    matched: list[dict[str, Any]] = []
    for note in notes:
        if not evaluate_filter_node(target_base.get("filters"), note):
            continue
        if selected_view and not evaluate_filter_node(selected_view.get("filters"), note):
            continue
        if proj_targets and not _matches_project(note, proj_targets):
            continue
        fm = note["fm"]
        note_status = str(fm.get("status") or "").strip().lower()
        if include_done is False and note_status == "done":
            continue
        if pillar_low and str(fm.get("pillar") or "").strip().lower() != pillar_low:
            continue
        if status_low and note_status != status_low:
            continue
        if today is not None and (fm.get("today") is True) != bool(today):
            continue
        if cadence_low and str(fm.get("cadence") or "").strip().lower() != cadence_low:
            continue
        if search_low:
            haystack = " ".join(
                [
                    note["file_name"],
                    note["title"],
                    str(fm.get("action") or ""),
                    _note_project_stem(note),
                    str(fm.get("pillar") or ""),
                ]
            ).lower()
            if search_low not in haystack:
                continue
        matched.append(note)

    matched.sort(key=lambda n: _sort_key_for_view(n, selected_view))

    group_counts: dict[str, int] = {}
    group_order_seen: list[str] = []
    for n in matched:
        gl = _group_label(n, selected_view)
        if gl is not None:
            if gl not in group_counts:
                group_counts[gl] = 0
                group_order_seen.append(gl)
            group_counts[gl] += 1

    groups_summary = [{"group": g, "count": group_counts[g]} for g in group_order_seen]
    columns = selected_view.get("order") if selected_view else []
    cap = max(1, min(int(limit or 25), 200))
    shown_notes = matched[:cap]

    return {
        "vault_path": vault_abs,
        "base": target_base["rel_path"],
        "base_uri": target_base["file_uri"],
        "view": selected_view["name"] if selected_view else "All",
        "view_type": selected_view["type"] if selected_view else "table",
        "columns": columns,
        "property_labels": target_base["properties"],
        "total_matched": len(matched),
        "returned_count": len(shown_notes),
        "truncated": len(matched) > len(shown_notes),
        "groups": groups_summary,
        "items": [_format_note_row(n, columns=columns) for n in shown_notes],
    }


def _derive_status_order_from_tasks_base(vault_abs: str) -> list[str]:
    """Read status priority order dynamically from Tasks.base groupOrder if present."""
    tasks_base_path = os.path.join(vault_abs, "Tasks.base")
    if os.path.exists(tasks_base_path):
        try:
            with open(tasks_base_path, "r", encoding="utf-8", errors="replace") as f:
                spec = yaml.safe_load(f.read()) or {}
            for v in spec.get("views") or []:
                if not isinstance(v, dict):
                    continue
                gb = v.get("groupBy")
                gb_prop = str(gb.get("property") if isinstance(gb, dict) else gb or "").strip().lower()
                if gb_prop == "status" and isinstance(v.get("groupOrder"), list):
                    derived = [
                        str(x).strip().lower()
                        for x in v["groupOrder"]
                        if x is not None and str(x).strip()
                    ]
                    if derived:
                        if "backlog" not in derived:
                            # Insert backlog before locked/done if present
                            idx = len(derived)
                            for marker in ("locked", "done"):
                                if marker in derived:
                                    idx = min(idx, derived.index(marker))
                            derived.insert(idx, "backlog")
                        return derived
        except Exception:
            pass
    return list(DEFAULT_STATUS_FALLBACK)


def list_tasks(
    vault_path: str,
    project: str = "",
    pillar: str = "",
    status: str = "",
    today: bool | None = None,
    cadence: str = "",
    search: str = "",
    include_done: bool = False,
    include_locked: bool = False,
    limit: int = 10,
) -> dict[str, Any]:
    """List prioritized tasks across all projects directly from 02-Tasks without hardcoding."""
    vault_abs = _require_vault(vault_path)
    notes = _scan_notes(vault_abs, subfolder="02-Tasks")
    status_order = _derive_status_order_from_tasks_base(vault_abs)
    status_rank_map = {s: idx for idx, s in enumerate(status_order)}

    proj_targets = _resolve_project_targets(vault_abs, project) if project.strip() else set()
    pillar_low = pillar.strip().lower()
    status_low = status.strip().lower()
    cadence_low = cadence.strip().lower()
    search_low = search.strip().lower()

    counts = {
        "total_active": 0,
        "today": 0,
        "doing": 0,
        "sprint": 0,
        "backlog": 0,
        "locked": 0,
        "done": 0,
        "by_project": {},
        "by_pillar": {},
    }

    matched: list[dict[str, Any]] = []
    for note in notes:
        fm = note["fm"]
        if fm.get("type") and str(fm.get("type")).strip().lower() != "task":
            continue
        if proj_targets and not _matches_project(note, proj_targets):
            continue
        if pillar_low and str(fm.get("pillar") or "").strip().lower() != pillar_low:
            continue
        if cadence_low and str(fm.get("cadence") or "").strip().lower() != cadence_low:
            continue

        note_status_raw = str(fm.get("status") or "Backlog").strip()
        note_status_low = note_status_raw.lower()
        is_today = fm.get("today") is True

        # Tally global scoped counts (respecting project/pillar/cadence) before status filtering
        if note_status_low == "done":
            counts["done"] += 1
        elif note_status_low == "locked":
            counts["locked"] += 1
        else:
            counts["total_active"] += 1
            if is_today:
                counts["today"] += 1
            if note_status_low == "doing":
                counts["doing"] += 1
            elif note_status_low == "sprint":
                counts["sprint"] += 1
            else:
                counts["backlog"] += 1
            p_name = _note_project_stem(note) or "General"
            pil_name = str(fm.get("pillar") or "").strip() or "Unassigned"
            counts["by_project"][p_name] = counts["by_project"].get(p_name, 0) + 1
            counts["by_pillar"][pil_name] = counts["by_pillar"].get(pil_name, 0) + 1

        if note_status_low == "done" and not include_done and status_low != "done":
            continue
        if note_status_low == "locked" and not include_locked and status_low != "locked":
            continue
        if status_low and note_status_low != status_low:
            continue
        if today is not None and is_today != bool(today):
            continue
        if search_low:
            haystack = " ".join(
                [
                    note["file_name"],
                    note["title"],
                    str(fm.get("action") or ""),
                    _note_project_stem(note),
                    str(fm.get("pillar") or ""),
                ]
            ).lower()
            if search_low not in haystack:
                continue

        matched.append(note)

    def _task_sort_key(n: dict[str, Any]) -> tuple:
        fm = n["fm"]
        st = str(fm.get("status") or "Backlog").strip().lower()
        st_rank = status_rank_map.get(st, len(status_rank_map))
        return (
            0 if fm.get("today") is True else 1,
            st_rank,
            _priority_rank(fm.get("priority")),
            n["file_name"].lower(),
        )

    matched.sort(key=_task_sort_key)
    cap = max(1, min(int(limit or 10), 200))
    shown = matched[:cap]

    return {
        "vault_path": vault_abs,
        "status_order_source": "Tasks.base" if os.path.exists(os.path.join(vault_abs, "Tasks.base")) else "default",
        "counts": counts,
        "total_matched": len(matched),
        "returned_count": len(shown),
        "truncated": len(matched) > len(shown),
        "items": [_format_note_row(n) for n in shown],
    }


def get_vault_overview(vault_path: str, cwd: str = "", config_path: str | None = None) -> dict[str, Any]:
    """Return full Vault state, active workspace project detection, projects, cohorts, drafts, and bases."""
    vault_abs = _require_vault(vault_path)
    hub = roh.resolve_hub(cwd=cwd, config_path=config_path, vault_override=vault_abs)
    bases = list_bases_summary(vault_abs)["bases"]
    projects_raw = roh.scan_projects(vault_abs)
    task_summary = list_tasks(vault_abs, limit=200)

    projects_out = []
    for p in projects_raw:
        p_tasks = roh.collect_project_tasks(vault_abs, p["name"], lang="en", limit=3)
        projects_out.append(
            {
                "name": p["name"],
                "pillar": p["pillar"],
                "status": p["status"],
                "workspace": p["workspace"],
                "parent": p["parent"],
                "aliases": p["aliases"],
                "has_scorecard": p["has_scorecard"],
                "active_total": p_tasks[0]["active_total"],
                "today_count": p_tasks[0]["today_count"],
                "locked_count": p_tasks[0]["locked_count"],
                "backlog_count": p_tasks[0]["backlog_count"],
                "file_uri": _as_file_uri(p["path"]),
            }
        )

    cohorts: list[dict[str, Any]] = []
    for note in _scan_notes(vault_abs, subfolder="00-Focus/Cohorts"):
        fm = note["fm"]
        st = str(fm.get("status") or "").strip()
        if st in ("Active", "Pulse-Check"):
            cohorts.append(
                {
                    "title": note["title"],
                    "status": st,
                    "project": roh._extract_link_stem(fm.get("project")),
                    "pillar": str(fm.get("pillar") or "").strip(),
                    "quota_completed": fm.get("quota_completed"),
                    "quota_target": fm.get("quota_target"),
                    "end_date": _norm_scalar(fm.get("end_date")),
                    "file_uri": note["file_uri"],
                }
            )

    draft_decisions: list[dict[str, Any]] = []
    for note in _scan_notes(vault_abs, subfolder="00-Focus/Decisions"):
        fm = note["fm"]
        st = str(fm.get("status") or "").strip().lower()
        if st in ("draft", "pending", "open", "in-progress", "in progress"):
            draft_decisions.append(
                {
                    "title": note["title"],
                    "status": fm.get("status"),
                    "project": roh._extract_link_stem(fm.get("project")),
                    "file_uri": note["file_uri"],
                }
            )

    return {
        "vault_path": vault_abs,
        "home_uri": _as_file_uri(os.path.join(vault_abs, "00-Home.md"))
        if os.path.exists(os.path.join(vault_abs, "00-Home.md"))
        else _as_file_uri(vault_abs),
        "workspace_state": hub["state"],
        "workspace_mode": hub["workspace_mode"],
        "detected_project": hub["detected_project"],
        "umbrella_project": hub["umbrella_project"],
        "stats": hub["stats"],
        "task_counts": task_summary["counts"],
        "projects": projects_out,
        "active_cohorts": cohorts,
        "pending_decisions": draft_decisions,
        "bases": bases,
    }


def _rewrite_frontmatter_preserving_body(abs_path: str, updater) -> dict[str, Any]:
    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
        orig_text = f.read()

    m = FM_RE.match(orig_text)
    line_ending = "\r\n" if "\r\n" in orig_text else "\n"
    if m:
        body = orig_text[m.end():]
        try:
            fm = yaml.safe_load(m.group(1))
            if not isinstance(fm, dict):
                fm = {}
        except Exception:
            fm = {}
    else:
        body = (line_ending + orig_text) if orig_text else line_ending
        fm = {}

    fm_updated = updater(dict(fm))
    dumped = yaml.safe_dump(
        fm_updated,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
    if line_ending != "\n":
        dumped = dumped.replace("\n", line_ending)

    new_text = f"---{line_ending}{dumped}{line_ending}---{body}"
    with open(abs_path, "w", encoding="utf-8", newline="") as f:
        f.write(new_text)
    return fm_updated


def _resolve_task_file(vault_abs: str, task_ref: str) -> dict[str, Any]:
    ref = str(task_ref or "").strip()
    if not ref:
        raise ValueError("task_ref must not be empty.")

    tasks_dir = os.path.abspath(os.path.join(vault_abs, "02-Tasks"))
    if not os.path.isdir(tasks_dir):
        raise ValueError("02-Tasks directory does not exist in Vault.")

    ref_posix = ref.replace("\\", "/")
    if os.path.isabs(ref) or ".." in ref_posix.split("/"):
        raise ValueError(f"Task reference '{task_ref}' escapes 02-Tasks directory.")

    # Direct relative path check (confined strictly to 02-Tasks)
    if "/" in ref_posix:
        cand = ref if ref_posix.lower().startswith("02-tasks/") else os.path.join("02-Tasks", ref)
        full = os.path.abspath(os.path.join(vault_abs, cand))
        if os.path.commonpath([tasks_dir, full]) != tasks_dir:
            raise ValueError(f"Task reference '{task_ref}' escapes 02-Tasks directory.")
        if os.path.isfile(full) and full.endswith(".md"):
            return parse_note(full, vault_abs)

    notes = _scan_notes(vault_abs, subfolder="02-Tasks")
    ref_stem = roh._extract_link_stem(ref)
    if ref_stem.lower().endswith(".md"):
        ref_stem = ref_stem[:-3]
    ref_low = ref_stem.lower()

    exact = [
        n
        for n in notes
        if n["file_name"].lower() == ref_low or n["rel_path"].lower() == ref_posix.lower()
    ]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        cands = ", ".join(n["rel_path"] for n in exact[:8])
        raise ValueError(f"Multiple tasks matched '{task_ref}': {cands}")

    partial = [
        n
        for n in notes
        if ref_low in n["file_name"].lower() or ref_low in n["title"].lower()
    ]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        cands = ", ".join(n["rel_path"] for n in partial[:8])
        raise ValueError(f"Ambiguous task reference '{task_ref}'. Matching candidates: {cands}")

    raise ValueError(f"Task '{task_ref}' not found in 02-Tasks.")


def _normalize_status_input(raw_status: str) -> str:
    txt = str(raw_status or "").strip()
    canonical = {
        "backlog": "Backlog",
        "sprint": "Sprint",
        "doing": "Doing",
        "locked": "Locked",
        "done": "Done",
        "todo": "Todo",
    }
    return canonical.get(txt.lower(), txt)


def _depends_matches(depends_raw: Any, blocker_stem_low: str) -> bool:
    if not depends_raw:
        return False
    items = depends_raw if isinstance(depends_raw, list) else [depends_raw]
    for item in items:
        stem = roh._extract_link_stem(item).strip()
        if stem.lower().endswith(".md"):
            stem = stem[:-3]
        if stem.lower() == blocker_stem_low:
            return True
    return False


def update_task(
    vault_path: str,
    task_ref: str,
    status: str | None = None,
    today: bool | None = None,
    day: str | None = None,
    action: str | None = None,
    priority: str | None = None,
) -> dict[str, Any]:
    """Update a task note safely inside 02-Tasks, preserving body and auto-unlocking dependents on Done."""
    vault_abs = _require_vault(vault_path)
    target = _resolve_task_file(vault_abs, task_ref)

    prev_status = str(target["fm"].get("status") or "").strip()
    norm_status = _normalize_status_input(status) if status is not None and str(status).strip() else None

    if norm_status is None and today is None and day is None and action is None and priority is None:
        raise ValueError("No fields specified to update (pass status, today, day, action, or priority).")

    def _apply_updates(fm: dict[str, Any]) -> dict[str, Any]:
        if norm_status is not None:
            fm["status"] = norm_status
            if norm_status.lower() == "done":
                fm["today"] = True if today is True else False
                fm["completed"] = datetime.date.today().isoformat()
        if today is not None and not (norm_status and norm_status.lower() == "done" and today is True):
            fm["today"] = bool(today)
        if day is not None:
            fm["day"] = str(day)
        if action is not None:
            fm["action"] = str(action).strip()
        if priority is not None:
            fm["priority"] = str(priority).strip()
        return fm

    updated_fm = _rewrite_frontmatter_preserving_body(target["abs_path"], _apply_updates)

    unlocked: list[dict[str, str]] = []
    if norm_status and norm_status.lower() == "done":
        blocker_low = target["file_name"].lower()
        for cand in _scan_notes(vault_abs, subfolder="02-Tasks"):
            if cand["abs_path"] == target["abs_path"]:
                continue
            cand_status = str(cand["fm"].get("status") or "").strip().lower()
            if cand_status == "locked" and _depends_matches(cand["fm"].get("depends_on"), blocker_low):
                _rewrite_frontmatter_preserving_body(
                    cand["abs_path"],
                    lambda cfm: {**cfm, "status": "Sprint"},
                )
                unlocked.append(
                    {
                        "file_name": cand["file_name"],
                        "rel_path": cand["rel_path"],
                        "file_uri": cand["file_uri"],
                    }
                )

    refreshed = parse_note(target["abs_path"], vault_abs)
    return {
        "updated": True,
        "previous_status": prev_status,
        "task": _format_note_row(refreshed),
        "completed": str(updated_fm.get("completed") or ""),
        "unlocked_tasks": unlocked,
    }
