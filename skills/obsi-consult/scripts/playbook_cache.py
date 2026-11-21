#!/usr/bin/env python3
"""
playbook_cache.py
Standalone CLI utility for managing obsi-consult cached Market Playbooks (zero duplicate searches).
"""
import argparse
import datetime
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_PLAYBOOKS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "playbooks")
)


def find_cached_playbook(playbooks_dir: str, query_text: str, default_ttl: int = 90) -> dict:
    index_path = os.path.join(playbooks_dir, "index.json")
    if not os.path.exists(index_path):
        return {"status": "MISS", "entry": None, "content": "", "matched_keywords": [], "age_days": None}

    with open(index_path, "r", encoding="utf-8", errors="replace") as f:
        index_data = json.load(f)

    q_lower = str(query_text or "").lower()
    best_entry = None
    best_matched: list[str] = []

    for entry in index_data.get("entries") or []:
        keywords = entry.get("keywords") or []
        matched = [kw for kw in keywords if str(kw).lower() in q_lower]
        if len(matched) < 2:
            continue
        if best_entry is None or (
            len(matched),
            str(entry.get("last_verified") or ""),
        ) > (
            len(best_matched),
            str(best_entry.get("last_verified") or ""),
        ):
            best_entry = entry
            best_matched = matched

    if best_entry is None:
        return {"status": "MISS", "entry": None, "content": "", "matched_keywords": [], "age_days": None}

    md_path = os.path.join(playbooks_dir, str(best_entry.get("file") or ""))
    if not os.path.exists(md_path):
        return {"status": "MISS", "entry": None, "content": "", "matched_keywords": [], "age_days": None}

    with open(md_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    ttl = int(best_entry.get("ttl_days") or index_data.get("default_ttl_days") or default_ttl)
    lv_str = str(best_entry.get("last_verified") or "")
    try:
        age_days = (datetime.date.today() - datetime.date.fromisoformat(lv_str)).days
    except ValueError:
        age_days = ttl + 1

    status = "STALE" if age_days > ttl else "HIT"
    return {
        "status": status,
        "entry": best_entry,
        "content": content,
        "matched_keywords": best_matched,
        "age_days": age_days,
    }


def save_playbook(
    playbooks_dir: str,
    slug: str,
    title: str,
    keywords: list[str],
    body_text: str,
    sources: list[str],
    ttl_days: int = 90,
    geo: str = "Global",
) -> dict:
    os.makedirs(playbooks_dir, exist_ok=True)
    today = datetime.date.today().isoformat()
    filename = f"{slug}.md"
    md_path = os.path.join(playbooks_dir, filename)

    clean_body = body_text.strip()
    if not clean_body.startswith("---"):
        sources_md = "\n".join(f"- {u}" for u in sources if u.strip())
        clean_body = (
            f"---\n"
            f"type: market-playbook\n"
            f"slug: {slug}\n"
            f"title: {json.dumps(title, ensure_ascii=False)}\n"
            f"last_verified: {today}\n"
            f"ttl_days: {ttl_days}\n"
            f"geo: {geo}\n"
            f"---\n\n"
            f"# Market Playbook: {title}\n\n"
            f"{clean_body}\n"
            + (f"\n## Verified Sources\n{sources_md}\n" if sources_md else "")
        )

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(clean_body.rstrip() + "\n")

    index_path = os.path.join(playbooks_dir, "index.json")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8", errors="replace") as f:
            index_data = json.load(f)
    else:
        index_data = {"version": 1, "default_ttl_days": ttl_days, "entries": []}

    new_entry = {
        "slug": slug,
        "title": title,
        "file": filename,
        "last_verified": today,
        "ttl_days": ttl_days,
        "geo": geo,
        "keywords": [k.strip() for k in keywords if k.strip()],
        "sources": [s.strip() for s in sources if s.strip()],
    }
    entries = [e for e in (index_data.get("entries") or []) if e.get("slug") != slug]
    entries.append(new_entry)
    index_data["entries"] = entries

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return {"saved_file": md_path, "index_file": index_path, "entry": new_entry}


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect or save Market Playbooks cache.")
    parser.add_argument("--playbooks-dir", default=DEFAULT_PLAYBOOKS_DIR, help="Path to playbooks directory")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_lookup = sub.add_parser("lookup", help="Look up cached playbook for query text")
    p_lookup.add_argument("--query", required=True, help="Domain/vision text to match keywords against")
    p_lookup.add_argument("--ttl", type=int, default=90, help="Default TTL days")
    p_lookup.add_argument("--json", action="store_true", help="Print JSON output")

    p_save = sub.add_parser("save", help="Save or update a market playbook")
    p_save.add_argument("--slug", required=True)
    p_save.add_argument("--title", required=True)
    p_save.add_argument("--keywords", required=True, help="Comma-separated keywords")
    p_save.add_argument("--body-file", required=True, help="Path to Markdown body file")
    p_save.add_argument("--sources", default="", help="Comma-separated source URLs")
    p_save.add_argument("--ttl", type=int, default=90)
    p_save.add_argument("--geo", default="Global")

    args = parser.parse_args()
    if args.cmd == "lookup":
        res = find_cached_playbook(args.playbooks_dir, args.query, default_ttl=args.ttl)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            slug = res["entry"]["slug"] if res.get("entry") else "(none)"
            print(f"{res['status']}: {slug} (age={res['age_days']}d, matched={res['matched_keywords']})")
        sys.exit(0)
    elif args.cmd == "save":
        with open(args.body_file, "r", encoding="utf-8", errors="replace") as f:
            body_txt = f.read()
        out = save_playbook(
            args.playbooks_dir,
            args.slug,
            args.title,
            args.keywords.split(","),
            body_txt,
            args.sources.split(",") if args.sources else [],
            ttl_days=args.ttl,
            geo=args.geo,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
