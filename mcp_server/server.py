#!/usr/bin/env python3
"""
server.py
Zero-dependency Stdio JSON-RPC 2.0 MCP Server for Obsi Founder Compass.
Never writes logs or non-JSON lines to stdout; diagnostics go to stderr only.
"""
from __future__ import annotations

import io
import json
import os
import sys
import traceback
from typing import Any

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import vault_engine as ve  # noqa: E402

SERVER_NAME = "obsi-founder-compass"
SERVER_VERSION = "0.2.0"
SUPPORTED_PROTOCOLS = ("2025-03-26", "2024-11-05")
DEFAULT_PROTOCOL = "2025-03-26"

TOOLS_SPEC = [
    {
        "name": "list_tasks",
        "title": "List Obsidian Vault Tasks",
        "description": (
            "Read live active tasks across all projects (or filtered by project, alias, pillar, "
            "status, today, cadence, or keyword) directly from the user's Obsidian Vault configured "
            "in ~/.gemini/config/brain-os.json, ranked dynamically using Tasks.base order."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Optional project name or alias filter"},
                "pillar": {"type": "string", "description": "Optional life/work pillar filter"},
                "status": {"type": "string", "description": "Optional status filter (e.g. Doing, Sprint, Backlog, Locked, Done)"},
                "today": {"type": "boolean", "description": "If true/false, filter by `today` flag"},
                "cadence": {"type": "string", "description": "Optional cadence filter (finite | recurring)"},
                "search": {"type": "string", "description": "Optional keyword search across title, action, project, pillar"},
                "include_done": {"type": "boolean", "default": False, "description": "Include Done tasks"},
                "include_locked": {"type": "boolean", "default": False, "description": "Include Locked tasks"},
                "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 200},
            },
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "query_base",
        "title": "Query Obsidian Base View",
        "description": (
            "Execute any Obsidian .base file (e.g. Today.base, Weekly.base, Tasks.base, Cohorts.base, "
            "Projects.base, or any user-created *.base) dynamically by parsing its YAML filters, "
            "groupBy/groupOrder, and sort rules without hardcoded schemas."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "base": {"type": "string", "description": "Base name or relative path (defaults to Tasks.base)"},
                "view": {"type": "string", "description": "View name inside the .base file (defaults to first view, or '*' for base-level filter only)"},
                "project": {"type": "string", "description": "Optional extra project/alias filter"},
                "pillar": {"type": "string", "description": "Optional extra pillar filter"},
                "status": {"type": "string", "description": "Optional extra status filter"},
                "today": {"type": "boolean", "description": "Optional extra today flag filter"},
                "cadence": {"type": "string", "description": "Optional extra cadence filter"},
                "search": {"type": "string", "description": "Optional keyword search"},
                "include_done": {"type": "boolean", "description": "Set false to exclude Done items"},
                "limit": {"type": "integer", "default": 25, "minimum": 1, "maximum": 200},
            },
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "list_bases",
        "title": "List Obsidian Bases",
        "description": "Discover all *.base files in the user's Obsidian Vault along with their views and property display labels.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "get_vault_overview",
        "title": "Get Obsidian Vault Overview",
        "description": "Return overall Vault stats, detected project for a workspace path (if cwd is passed), projects with task counts, active cohorts, pending decision drafts, and available .base views.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cwd": {"type": "string", "description": "Optional current workspace directory to detect matching Vault project(s)"},
            },
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "update_task",
        "title": "Update Obsidian Task",
        "description": (
            "Update an Obsidian task card inside 02-Tasks/ (status, today, day, action, priority). "
            "When status becomes Done, sets today: false, sets completed date, and auto-unlocks dependent Locked tasks to Sprint. "
            "Always confirm in 1 line with the user before mutating unless the user explicitly instructed the update."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_ref": {"type": "string", "description": "Task filename stem, title fragment, or relative path inside 02-Tasks/"},
                "status": {"type": "string", "description": "New status (e.g. Doing, Sprint, Backlog, Locked, Done)"},
                "today": {"type": "boolean", "description": "Pin/unpin in Today.base"},
                "day": {"type": "string", "description": "Weekly day slot (e.g. Sun, شنبه)"},
                "action": {"type": "string", "description": "Half-line concrete next action"},
                "priority": {"type": "string", "description": "Priority (High, Medium, Low)"},
            },
            "required": ["task_ref"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
]


def _format_tasks_markdown(res: dict[str, Any]) -> str:
    counts = res["counts"]
    header = (
        f"**Active tasks:** {counts['total_active']} "
        f"(Today: {counts['today']} · Doing: {counts['doing']} · Sprint: {counts['sprint']} · "
        f"Backlog: {counts['backlog']} · Locked: {counts['locked']})\n"
        f"Showing {res['returned_count']} of {res['total_matched']} matched tasks:"
    )
    lines = [header]
    for idx, item in enumerate(res["items"], 1):
        star = "⭐ " if item["today"] else ""
        proj = item["project"] or "General"
        act = f" — {item['action']}" if item["action"] else ""
        lines.append(
            f"{idx}. {star}**[{proj}]** [{item['file_name']}]({item['file_uri']}) "
            f"(`{item['status']}` · {item['priority'] or '-'}){act}"
        )
    return "\n".join(lines)


def _format_base_markdown(res: dict[str, Any]) -> str:
    lines = [
        f"**Base:** [{res['base']}]({res['base_uri']}) · **View:** `{res['view']}` ({res['view_type']})",
        f"Matched: {res['total_matched']} · Showing: {res['returned_count']}",
    ]
    if res["groups"]:
        grp = " · ".join(f"{g['group']}: {g['count']}" for g in res["groups"])
        lines.append(f"**Groups:** {grp}")
    for idx, item in enumerate(res["items"], 1):
        star = "⭐ " if item["today"] else ""
        proj = item["project"] or item["pillar"] or "-"
        st = item["status"] or "-"
        act = f" — {item['action']}" if item["action"] else ""
        lines.append(f"{idx}. {star}[{item['file_name']}]({item['file_uri']}) (`{proj}` · `{st}`){act}")
    return "\n".join(lines)


def _format_bases_markdown(res: dict[str, Any]) -> str:
    lines = [f"**Discovered Bases ({res['count']}):**"]
    for b in res["bases"]:
        views = ", ".join(f"{v['name']} ({v['type']})" for v in b["views"]) or "no views"
        lines.append(f"- [{b['rel_path']}]({b['file_uri']}) — {views}")
    return "\n".join(lines)


def _format_overview_markdown(res: dict[str, Any]) -> str:
    tc = res["task_counts"]
    lines = [
        f"**Vault:** [{res['vault_path']}]({res['home_uri']})",
        f"**Tasks:** {tc['total_active']} active ({tc['today']} today · {tc['doing']} doing · {tc['sprint']} sprint · {tc['locked']} locked)",
    ]
    if res.get("detected_project"):
        lines.append(f"**Detected Workspace Project:** {res['detected_project']}")
    lines.append(f"**Projects:** {len(res['projects'])} · **Active Cohorts:** {len(res['active_cohorts'])} · **Pending Decisions:** {len(res['pending_decisions'])} · **Bases:** {len(res['bases'])}")
    return "\n".join(lines)


def _format_update_markdown(res: dict[str, Any]) -> str:
    t = res["task"]
    msg = (
        f"Updated [{t['file_name']}]({t['file_uri']}): "
        f"`{res['previous_status'] or '-'}` -> `{t['status']}` (`today={t['today']}`)"
    )
    if res["unlocked_tasks"]:
        unlocked_links = ", ".join(f"[{u['file_name']}]({u['file_uri']})" for u in res["unlocked_tasks"])
        msg += f"\nUnlocked to Sprint: {unlocked_links}"
    return msg


def _call_tool(
    name: str,
    arguments: dict[str, Any],
    config_path: str | None = None,
    vault_override: str = "",
) -> dict[str, Any]:
    ctx = ve.load_vault_context(config_path=config_path, vault_override=vault_override)
    if not ctx["configured"]:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Obsidian Vault is not configured yet (missing valid vault_path in "
                        "~/.gemini/config/brain-os.json). Ask the user to run /obsi-setup."
                    ),
                }
            ],
            "isError": True,
        }

    vp = ctx["vault_path"]
    args = arguments if isinstance(arguments, dict) else {}

    if name == "list_tasks":
        data = ve.list_tasks(
            vp,
            project=str(args.get("project") or ""),
            pillar=str(args.get("pillar") or ""),
            status=str(args.get("status") or ""),
            today=args.get("today") if isinstance(args.get("today"), bool) else None,
            cadence=str(args.get("cadence") or ""),
            search=str(args.get("search") or ""),
            include_done=bool(args.get("include_done", False)),
            include_locked=bool(args.get("include_locked", False)),
            limit=int(args.get("limit", 10)),
        )
        return {"content": [{"type": "text", "text": _format_tasks_markdown(data)}], "structuredContent": data, "isError": False}

    if name == "query_base":
        inc_done = args.get("include_done")
        data = ve.query_base(
            vp,
            base=str(args.get("base") or ""),
            view=str(args.get("view") or ""),
            project=str(args.get("project") or ""),
            pillar=str(args.get("pillar") or ""),
            status=str(args.get("status") or ""),
            today=args.get("today") if isinstance(args.get("today"), bool) else None,
            cadence=str(args.get("cadence") or ""),
            search=str(args.get("search") or ""),
            include_done=inc_done if isinstance(inc_done, bool) else None,
            limit=int(args.get("limit", 25)),
        )
        return {"content": [{"type": "text", "text": _format_base_markdown(data)}], "structuredContent": data, "isError": False}

    if name == "list_bases":
        data = ve.list_bases_summary(vp)
        return {"content": [{"type": "text", "text": _format_bases_markdown(data)}], "structuredContent": data, "isError": False}

    if name == "get_vault_overview":
        data = ve.get_vault_overview(
            vp,
            cwd=str(args.get("cwd") or ""),
            config_path=ctx["config_path"],
        )
        return {"content": [{"type": "text", "text": _format_overview_markdown(data)}], "structuredContent": data, "isError": False}

    if name == "update_task":
        data = ve.update_task(
            vp,
            task_ref=str(args.get("task_ref") or ""),
            status=args.get("status"),
            today=args.get("today") if isinstance(args.get("today"), bool) else None,
            day=args.get("day"),
            action=args.get("action"),
            priority=args.get("priority"),
        )
        return {"content": [{"type": "text", "text": _format_update_markdown(data)}], "structuredContent": data, "isError": False}

    raise KeyError(f"Unknown tool: {name}")


def _list_resources(config_path: str | None = None, vault_override: str = "") -> list[dict[str, Any]]:
    resources = [
        {
            "uri": "obsi://overview",
            "name": "Vault Overview",
            "description": "Live Obsidian Vault summary, project task counts, cohorts, and pending decisions.",
            "mimeType": "application/json",
        }
    ]
    ctx = ve.load_vault_context(config_path=config_path, vault_override=vault_override)
    if ctx["configured"]:
        for b in ve.discover_bases(ctx["vault_path"]):
            resources.append(
                {
                    "uri": f"obsi://base/{b['rel_path']}",
                    "name": f"Base: {b['name']}",
                    "description": f"Live query results for {b['rel_path']} (default view).",
                    "mimeType": "application/json",
                }
            )
    return resources


def _read_resource(uri: str, config_path: str | None = None, vault_override: str = "") -> dict[str, Any]:
    ctx = ve.load_vault_context(config_path=config_path, vault_override=vault_override)
    if not ctx["configured"]:
        raise ValueError("Obsidian Vault is not configured.")
    vp = ctx["vault_path"]

    if uri == "obsi://overview":
        payload = ve.get_vault_overview(vp, config_path=ctx["config_path"])
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(payload, ensure_ascii=False, indent=2),
                }
            ]
        }

    prefix = "obsi://base/"
    if uri.startswith(prefix):
        rel = uri[len(prefix):]
        payload = ve.query_base(vp, base=rel)
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(payload, ensure_ascii=False, indent=2),
                }
            ]
        }

    raise ValueError(f"Unknown resource URI: {uri}")


def handle_request(
    req: dict[str, Any],
    config_path: str | None = None,
    vault_override: str = "",
) -> dict[str, Any] | None:
    """Process one JSON-RPC 2.0 MCP message and return response dict (or None for notifications)."""
    if not isinstance(req, dict):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}

    has_id = "id" in req
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params") or {}

    if not isinstance(method, str):
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32600, "message": "Invalid Request"}}

    # Notifications (no id, or notification/*)
    if not has_id or method.startswith("notifications/"):
        return None

    try:
        if method == "initialize":
            client_proto = str(params.get("protocolVersion") or "")
            proto = client_proto if client_proto in SUPPORTED_PROTOCOLS else DEFAULT_PROTOCOL
            result = {
                "protocolVersion": proto,
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                },
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": (
                    "Read and update the user's local Obsidian Native Bases Vault configured in "
                    "~/.gemini/config/brain-os.json without hardcoding project names or paths."
                ),
            }
            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS_SPEC}}

        if method == "tools/call":
            tool_name = str(params.get("name") or "")
            tool_args = params.get("arguments") or {}
            try:
                res = _call_tool(
                    tool_name,
                    tool_args,
                    config_path=config_path,
                    vault_override=vault_override,
                )
            except KeyError as exc:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": str(exc)}}
            except Exception as exc:
                res = {"content": [{"type": "text", "text": f"Error: {exc}"}], "isError": True}
            return {"jsonrpc": "2.0", "id": req_id, "result": res}

        if method == "resources/list":
            res_list = _list_resources(config_path=config_path, vault_override=vault_override)
            return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": res_list}}

        if method == "resources/read":
            uri = str(params.get("uri") or "")
            try:
                res = _read_resource(uri, config_path=config_path, vault_override=vault_override)
            except Exception as exc:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": str(exc)}}
            return {"jsonrpc": "2.0", "id": req_id, "result": res}

        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}

    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": f"Internal error: {exc}"}}


def main() -> None:
    stdin_stream = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")
    stdout_stream = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n")

    for raw_line in stdin_stream:
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception as exc:
            err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {exc}"}}
            stdout_stream.write(json.dumps(err_resp, ensure_ascii=False) + "\n")
            stdout_stream.flush()
            continue

        if isinstance(payload, list):
            responses = []
            for item in payload:
                resp = handle_request(item)
                if resp is not None:
                    responses.append(resp)
            if responses:
                stdout_stream.write(json.dumps(responses, ensure_ascii=False) + "\n")
                stdout_stream.flush()
        else:
            resp = handle_request(payload)
            if resp is not None:
                stdout_stream.write(json.dumps(resp, ensure_ascii=False) + "\n")
                stdout_stream.flush()


if __name__ == "__main__":
    main()
