#!/usr/bin/env python3
"""
extract_session_steps.py
Extracts dialogue and tool actions between step indices from transcript.jsonl
(with fallback recovery from transcript_full.jsonl for truncated fields).
"""
import argparse
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MARKER_RE = re.compile(r"(/obsi-consult|/obsi-inspect|/obsi-priority|/obsi-setup|/obsi\b|بازرس)")
INSPECT_RE = re.compile(r"(/obsi-inspect|بازرس)")
CONSULT_RE = re.compile(r"/obsi-consult")
IMPORTANT_ARGS = ("query", "Path", "CommandLine", "ScriptPath", "Description", "Action", "Target", "Args")


def clean_user_text(raw: str) -> str:
    txt = str(raw or "")
    txt = txt.replace("<USER_REQUEST>", "").replace("</USER_REQUEST>", "")
    if "<ADDITIONAL_METADATA>" in txt:
        txt = txt.split("<ADDITIONAL_METADATA>", 1)[0]
    if "<USER_SETTINGS_CHANGE>" in txt:
        txt = txt.split("<USER_SETTINGS_CHANGE>", 1)[0]
    return txt.strip()


def load_jsonl_dedup(path: str) -> list[dict]:
    by_step: dict[int, dict] = {}
    order: list[int] = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            idx = rec.get("step_index")
            if idx is None:
                continue
            if idx not in by_step:
                order.append(idx)
            by_step[idx] = rec
    return [by_step[i] for i in sorted(order)]


def recover_truncated(records: list[dict], full_log_path: str) -> list[dict]:
    needed = {r.get("step_index") for r in records if r.get("truncated_fields")}
    if not needed or not os.path.exists(full_log_path):
        return records
    recovered: dict[int, dict] = {}
    with open(full_log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            idx = rec.get("step_index")
            if idx in needed:
                recovered[idx] = rec
    return [recovered.get(r.get("step_index"), r) for r in records]


def format_tool_calls(tools: list[dict]) -> str:
    parts = []
    for t in tools:
        if not isinstance(t, dict):
            continue
        name = t.get("name") or t.get("tool") or "unknown_tool"
        args = t.get("arguments") if "arguments" in t else t.get("args", {})
        if not isinstance(args, dict):
            parts.append(f"{name}()")
            continue
        kv = []
        seen = set()
        for k in IMPORTANT_ARGS:
            if k in args and args[k] not in (None, ""):
                val = str(args[k]).replace("\n", " ").strip()
                if len(val) > 120:
                    val = val[:117] + "..."
                kv.append(f"{k}={val}")
                seen.add(k)
        extra = [k for k in args.keys() if k not in seen]
        if extra:
            kv.append("+" + ",".join(extra))
        parts.append(f"{name}({', '.join(kv)})")
    return "; ".join(parts)


def find_markers(records: list[dict]) -> list[tuple[int, str]]:
    hits = []
    for r in records:
        if r.get("type") != "USER_INPUT":
            continue
        clean = clean_user_text(r.get("content", ""))
        if MARKER_RE.search(clean):
            preview = " ".join(clean.split())
            if len(preview) > 120:
                preview = preview[:117] + "..."
            hits.append((r.get("step_index", 0), preview))
    return hits


def resolve_since_last_inspect(records: list[dict]) -> int:
    user_steps = [
        (r.get("step_index", 0), clean_user_text(r.get("content", "")))
        for r in records
        if r.get("type") == "USER_INPUT"
    ]
    if not user_steps:
        return 0
    _, last_txt = user_steps[-1]
    prior = user_steps[:-1] if INSPECT_RE.search(last_txt) else user_steps

    for idx, txt in reversed(prior):
        if INSPECT_RE.search(txt):
            return idx
    for idx, txt in reversed(prior):
        if CONSULT_RE.search(txt):
            return idx

    dialogue = [
        r for r in records
        if (r.get("type") == "USER_INPUT" and clean_user_text(r.get("content", "")))
        or (r.get("type") == "PLANNER_RESPONSE" and str(r.get("content") or "").strip())
    ]
    slice_recs = dialogue[-6:]
    return slice_recs[0].get("step_index", 0) if slice_recs else 0


def extract_session_steps(
    app_data_dir: str,
    conversation_id: str,
    start_step: int | None = None,
    end_step: int | None = None,
    last_n_dialogue: int | None = None,
    only_markers: bool = False,
    since_last_inspect: bool = False,
) -> str:
    log_dir = os.path.join(app_data_dir, "brain", conversation_id, ".system_generated", "logs")
    log_path = os.path.join(log_dir, "transcript.jsonl")
    full_path = os.path.join(log_dir, "transcript_full.jsonl")
    if not os.path.exists(log_path):
        return f"Error: log file not found at {log_path}"

    records = load_jsonl_dedup(log_path)

    if only_markers:
        hits = find_markers(records)
        if not hits:
            return "No /obsi or inspect markers found."
        return "\n".join(f"[Step {idx}] {prev}" for idx, prev in hits)

    if since_last_inspect and start_step is None:
        start_step = resolve_since_last_inspect(records)

    if start_step is not None:
        records = [r for r in records if r.get("step_index", 0) >= start_step]
    if end_step is not None:
        records = [r for r in records if r.get("step_index", 0) <= end_step]

    if last_n_dialogue is not None and start_step is None:
        dialogue = [
            r for r in records
            if (r.get("type") == "USER_INPUT" and clean_user_text(r.get("content", "")))
            or (r.get("type") == "PLANNER_RESPONSE" and str(r.get("content") or "").strip())
        ]
        target = dialogue[-last_n_dialogue:]
        min_idx = target[0].get("step_index", 0) if target else 0
        records = [r for r in records if r.get("step_index", 0) >= min_idx]

    records = recover_truncated(records, full_path)

    output_lines = []
    for r in records:
        idx = r.get("step_index")
        stype = r.get("type")
        source = r.get("source")
        content = str(r.get("content") or "")
        tools = r.get("tool_calls") or []

        if stype == "USER_INPUT":
            clean = clean_user_text(content)
            output_lines.append(f"### [Step {idx}] USER:\n{clean}\n")
        elif stype == "PLANNER_RESPONSE":
            if content.strip():
                output_lines.append(f"### [Step {idx}] ASSISTANT:\n{content.strip()}\n")
            if tools:
                output_lines.append(f"[Step {idx} TOOLS]: {format_tool_calls(tools)}\n")
        elif stype == "GENERIC" and source == "MODEL":
            flat = " ".join(content.split())
            if not flat:
                continue
            status = r.get("status")
            prefix = f"[Step {idx} RESULT" + (f" ({status})" if status and status != "DONE" else "") + "]: "
            if len(flat) > 240:
                flat = flat[:237] + "..."
            output_lines.append(f"{prefix}{flat}\n")

    return "\n".join(output_lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract steps from transcript.jsonl for inspector.")
    parser.add_argument(
        "--app-data-dir",
        default=os.path.expanduser(os.path.join("~", ".gemini", "antigravity")),
        help="Antigravity appDataDir",
    )
    parser.add_argument("--chat-id", required=True, help="Conversation ID")
    parser.add_argument("--start", type=int, default=None, help="Start step_index")
    parser.add_argument("--end", type=int, default=None, help="End step_index")
    parser.add_argument("--last-n", type=int, default=None, help="Last N non-empty dialogue turns")
    parser.add_argument("--find-markers", action="store_true", help="List USER_INPUT marker steps")
    parser.add_argument("--since-last-inspect", action="store_true", help="Auto-slice since last inspect/consult")

    args = parser.parse_args()
    print(
        extract_session_steps(
            args.app_data_dir,
            args.chat_id,
            args.start,
            args.end,
            args.last_n,
            only_markers=args.find_markers,
            since_last_inspect=args.since_last_inspect,
        )
    )


if __name__ == "__main__":
    main()
