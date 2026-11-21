"""Native Antigravity run_workflow script for obsi-consult 30,000-ft macro business & market gap audits."""

import datetime
import glob
import json
import os
import re

DEFAULT_CONFIG_PATH = os.path.expanduser(os.path.join("~", ".gemini", "config", "brain-os.json"))


def resolve_default_playbooks_dir() -> str:
    candidates = [
        os.path.expanduser(os.path.join("~", ".gemini", "config", "skills", "obsi-consult", "playbooks")),
    ] + sorted(
        glob.glob(
            os.path.expanduser(
                os.path.join("~", ".gemini", "config", "plugins", "*", "skills", "obsi-consult", "playbooks")
            )
        )
    )
    for c in candidates:
        if os.path.isdir(c):
            return c
    return candidates[0]


def load_brain_config(config_path: str | None = None) -> dict:
    path = config_path or DEFAULT_CONFIG_PATH
    cfg = {
        "vault_path": os.path.expanduser(os.path.join("~", "Obsidian", "FounderBrain")),
        "playbooks_dir": resolve_default_playbooks_dir(),
        "language": "auto",
        "scorecards_dir": "00-Focus/Scorecards",
        "decisions_dir": "00-Focus/Decisions",
        "cache_ttl_days": 90,
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


cfg = load_brain_config(args.get("config_path"))
project = args.get("project", "Target Project")
domain_model = args.get("domain_model", "Early-stage software or commerce venture")
vision = args.get("vision", "")
vault_path = args.get("vault_path") or cfg["vault_path"]
playbooks_dir = args.get("playbooks_dir") or cfg["playbooks_dir"]
language = args.get("language") or cfg.get("language", "auto")
cache_ttl_days = int(args.get("cache_ttl_days") or cfg["cache_ttl_days"])
scorecards_rel = cfg.get("scorecards_dir", "00-Focus/Scorecards")
force_refresh = bool(args.get("force_refresh", False))
mode = args.get("mode", "full")
focus_pillar = args.get("focus_pillar", "")
existing_scorecard = args.get("existing_scorecard", "")

NO_CAPACITY_POLICING = (
    "NO CAPACITY POLICING (ISOLATED SINGLE-PROJECT LENS): Focus 100% on THIS project's market, buyers, "
    "marketing, supply, monetization, and internal operations. NEVER ask about personal schedule/bandwidth, "
    "NEVER compare focus against other projects, NEVER lecture about 'splitting focus' "
    "across parallel businesses/projects, and NEVER advise parking/killing the project due to personal bandwidth "
    "(optional workload prioritization happens ONLY later as an advisory suggestion inside `/obsi-priority` "
    "before converting Visions into Cohorts/Tasks)."
)

NO_CODE_RULE = (
    "STRICTLY READ-ONLY & 30,000-FOOT BUSINESS/MARKET LAYER ONLY: "
    "NEVER write, edit, or mutate any files. "
    "NO-CODE FIREWALL: FORBIDDEN to inspect or read ANY source code or technical config files "
    "(.php, .vue, .ts, .js, .py, migrations, routes, controllers, backend/frontend app dirs, .agents/, git/server logs, or technical port drafts). "
    "FORBIDDEN to cite code file paths, class/method names, HTTP ports (8080, 443), CWV, LCP, INP, CLS, JSON-LD, REST API, SQL, Docker, SSH, migration, or coding checklists. "
    "Treat the website/platform build as a single 1-line business fact ('Website and product infrastructure are built and online'). "
    "Focus 100% on Market, Customer Demand, Competitors, Marketing & Acquisition Channels, Brand Trust, Partner/Supply Incentives, Pricing/Unit Economics, and Retention. "
    "Cite verified web URLs, cached playbooks, Vault strategy docs, or explicit founder statements — or mark unverified points with 'Assumption'. Never invent numbers."
)

VIBE_CODER_LENS = (
    f"VIBE-CODER 360 COACH LENS (Target output language: {language}, matching the founder's Vision language): "
    "Assume the founder is strong at building software/AI products but wants crystal-clear, jargon-free guidance "
    "on everything outside code (marketing, buyer psychology, competitors, sales, unit margins, repeat orders). "
    "Whenever any MBA/business acronym appears (e.g., AOV, CAC, ICP, Retention, Liquidity, Take Rate), immediately add a crisp 4-6 word plain explanation "
    "and avoid dry textbook phrasing."
)

BANNED_TECH_RE = re.compile(
    r"(\.(php|vue|ts|js|py)\b|Core Web Vitals|"
    r"\b(CWV|LCP|INP|CLS|JSON-LD|REST API|SQL|Docker|SSH|migration)\b|"
    r"8080|routes/api|controllers/)",
    re.I,
)


async def enforce_no_code_output(payload: dict, schema: dict, role_label: str) -> dict:
    raw = json.dumps(payload, ensure_ascii=False)
    leaks = sorted({m.group(0) for m in BANNED_TECH_RE.finditer(raw)})
    if not leaks:
        return payload
    log(f"No-Code Firewall caught leaked tech terms in {role_label}: {leaks}; running cleanup rewrite")
    rewrite_prompt = f"""{NO_CODE_RULE}
{VIBE_CODER_LENS}
Your previous JSON output leaked forbidden technical/code terms: {leaks}.
Rewrite the JSON payload strictly at the 30,000-foot business/market/customer/competitor level:
- Completely remove all mentions of {leaks}, source-code files, ports, and engineering jargon.
- Replace technical observations with pure business/marketing/conversion language.
- Keep all business substance, evidence tags, and market citations intact.

Original JSON:
{raw}

Call `finish` with valid JSON matching the exact schema."""
    return await agent(
        rewrite_prompt,
        schema=schema,
        role=f"{role_label} (No-Code Rewrite)",
        type_name="self",
        model="flash",
    )


if mode == "full":
    scorecards_abs = os.path.join(vault_path, scorecards_rel.replace("/", os.sep))
    cache_res = (
        {"status": "MISS", "entry": None, "content": "", "matched_keywords": [], "age_days": None}
        if force_refresh
        else find_cached_playbook(playbooks_dir, f"{domain_model} {vision}", default_ttl=cache_ttl_days)
    )

    progress_schema = {
        "type": "object",
        "properties": {
            "worked_on": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "business_pillar": {"type": "string"},
                        "evidence": {"type": "string"},
                        "summary": {"type": "string"},
                    },
                    "required": ["business_pillar", "evidence", "summary"],
                },
            },
            "untouched_or_weak": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "business_pillar": {"type": "string"},
                        "evidence": {"type": "string"},
                        "summary": {"type": "string"},
                    },
                    "required": ["business_pillar", "evidence", "summary"],
                },
            },
            "business_unknowns": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["worked_on", "untouched_or_weak", "business_unknowns"],
    }

    progress_prompt = f"""{NO_CODE_RULE}
{NO_CAPACITY_POLICING}
You are auditing high-level business/strategy progress for THIS single project ONLY (strictly NO code files, NO reading Monthly-Plans/ or judging personal bandwidth).
Allowed reads ONLY inside `{vault_path}`:
- `00-Focus/00-North-Star.md` (to check alignment with this project's goal only)
- Project note for `{project}` under `01-Projects/` (and existing `{os.path.join(scorecards_abs, f'{project}.md')}` if it exists)
- Any marketing strategy note in `03-Marketing/` relevant to `{project}`

Founder Vision Statement:
{vision}

Summarize cleanly:
1. `worked_on`: Which macro business areas the founder already executed or prepared.
2. `untouched_or_weak`: Which macro business areas show no execution plan or active work in strategy notes (e.g., marketing, acquisition channels, competitive differentiation, value pitch, retention, unit economics).
3. `business_unknowns`: Key off-disk commercial facts needed from the founder (target buyer persona, marketing channels/budget, pricing/margin, partner pitch).
Call `finish` with valid JSON."""

    if cache_res["status"] == "HIT":
        phase("Phase 1: Cached Playbook Hit + Founder Strategy Audit (0 Duplicate Searches)")
        entry = cache_res["entry"]
        log(f"Cache HIT: reusing playbook `{entry['slug']}` (age={cache_res['age_days']}d; 0 fresh web searches)")
        progress_data = await agent(
            progress_prompt,
            schema=progress_schema,
            role="Founder Progress & Strategy Auditor",
            type_name="self",
            model="flash",
        )
        market_source_block = (
            f"Verified Cached Market Playbook (`{entry['slug']}`, verified {entry.get('last_verified')}):\n"
            f"{cache_res['content']}"
        )
        research_trace = {
            "cache_status": "HIT",
            "playbook_slug": entry["slug"],
            "playbook_last_verified": entry.get("last_verified"),
            "matched_keywords": cache_res["matched_keywords"],
            "fresh_web_searches_run": 0,
            "search_queries_used": [],
            "save_playbook_suggestion": None,
        }
    else:
        phase("Phase 1: Parallel Market Pillars Research & Founder Strategy Audit")
        market_schema = {
            "type": "object",
            "properties": {
                "stage_name": {"type": "string"},
                "search_queries_used": {"type": "array", "items": {"type": "string"}},
                "suggested_playbook_slug": {"type": "string"},
                "suggested_keywords": {"type": "array", "items": {"type": "string"}},
                "pillars": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "why_it_matters_in_market": {"type": "string"},
                            "business_checklist": {"type": "array", "items": {"type": "string"}},
                            "market_experiments": {"type": "array", "items": {"type": "string"}},
                            "source_urls": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": [
                            "name",
                            "why_it_matters_in_market",
                            "business_checklist",
                            "market_experiments",
                            "source_urls",
                        ],
                    },
                },
            },
            "required": [
                "stage_name",
                "search_queries_used",
                "suggested_playbook_slug",
                "suggested_keywords",
                "pillars",
            ],
        }
        stale_note = (
            f"\nPrevious playbook `{cache_res['entry']['slug']}` is STALE (last_verified {cache_res['entry'].get('last_verified')}); refresh stale benchmarks."
            if cache_res["status"] == "STALE" and cache_res.get("entry")
            else ""
        )
        market_prompt = f"""{NO_CODE_RULE}
You are researching real-world business & market success pillars for an early-stage founder:
- Project: {project}
- Domain Model: {domain_model}
- Founder Vision & Runway: {vision}{stale_note}

Run targeted `search_web` queries ONLY on business, go-to-market, competitor positioning, marketing/acquisition channels, liquidity/activation, buyer trust, supplier/partner incentives, pricing/margins, and retention.
Produce 6 to 7 pure **Business & Market Pillars** (NO tech/code checklists) with business checklists, cheap marketing/sales validation experiments, real `source_urls`, exact `search_queries_used`, a clean kebab-case `suggested_playbook_slug`, and `suggested_keywords` for future caching.
Call `finish` with valid JSON."""

        market_data, progress_data = await parallel(
            [
                ("market", market_prompt, market_schema, "Market & Business Pillars Researcher"),
                ("progress", progress_prompt, progress_schema, "Founder Progress & Strategy Auditor"),
            ],
            lambda job: agent(job[1], schema=job[2], role=job[3], type_name="self", model="flash"),
        )
        market_source_block = json.dumps(market_data, ensure_ascii=False)
        queries_used = market_data.get("search_queries_used") or []
        research_trace = {
            "cache_status": cache_res["status"],
            "playbook_slug": market_data.get("suggested_playbook_slug", ""),
            "playbook_last_verified": None,
            "matched_keywords": cache_res["matched_keywords"],
            "fresh_web_searches_run": len(queries_used),
            "search_queries_used": queries_used,
            "save_playbook_suggestion": {
                "slug": market_data.get("suggested_playbook_slug", ""),
                "keywords": market_data.get("suggested_keywords", []),
                "sources": sorted(
                    {u for p in market_data.get("pillars", []) for u in p.get("source_urls", []) if u}
                ),
            },
        }

    phase("Phase 2: Macro Business Gap Synthesis (Vibe-Coder 360 Lens)")

    synthesis_schema = {
        "type": "object",
        "properties": {
            "project": {"type": "string"},
            "stage": {"type": "string"},
            "vision_summary": {"type": "string"},
            "worked_on_summary": {"type": "string"},
            "not_worked_on_summary": {"type": "string"},
            "scorecard": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "pillar": {"type": "string"},
                        "status": {"type": "string", "enum": ["Done", "Weak", "Missing"]},
                        "user_progress": {"type": "string"},
                        "gap_explanation": {"type": "string"},
                        "evidence_tag": {"type": "string"},
                        "priority_rank": {"type": "integer"},
                    },
                    "required": ["pillar", "status", "user_progress", "gap_explanation", "evidence_tag", "priority_rank"],
                },
            },
            "market_blind_spots_3": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "blind_spot": {"type": "string"},
                        "why_it_matters_in_market": {"type": "string"},
                        "evidence_or_source": {"type": "string"},
                        "strategic_consideration": {"type": "string"},
                    },
                    "required": ["blind_spot", "why_it_matters_in_market", "evidence_or_source", "strategic_consideration"],
                },
            },
            "macro_bundles": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "main_aspect": {"type": "string"},
                        "keep_in_mind_alongside": {"type": "array", "items": {"type": "string"}},
                        "why_it_unlocks_growth": {"type": "string"},
                    },
                    "required": ["title", "main_aspect", "keep_in_mind_alongside", "why_it_unlocks_growth"],
                },
            },
            "private_unknown_questions_max_3": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "project",
            "stage",
            "vision_summary",
            "worked_on_summary",
            "not_worked_on_summary",
            "scorecard",
            "market_blind_spots_3",
            "macro_bundles",
            "private_unknown_questions_max_3",
        ],
    }

    synth_prompt = f"""{NO_CODE_RULE}
{NO_CAPACITY_POLICING}
{VIBE_CODER_LENS}
Act as a friendly, honest 30,000-foot Business & Market Coach advising the Vibe-Coder founder of '{project}'.

Market Research / Playbook Pillars:
{market_source_block}

Founder Strategy & Progress:
{json.dumps(progress_data, ensure_ascii=False)}

Founder Vision:
{vision}

Rules:
- Stay 100% at the macro market/business level of THIS project (buyers, acquisition channels, positioning vs competitors, trust/brand, partner motivation, unit margins, repeat purchase). ZERO coding, tech metrics, ports, or file paths! ZERO capacity/bandwidth/multi-project lecturing!
- **Strategic Altitude Separation (NO premature micro-tactics):** In this full macro stage, DO NOT prescribe detailed campaign counts/quotas. Save concrete numerical experiments for `/obsi-priority` Cohorts or `deep_dive` later.
- In `worked_on_summary` & `not_worked_on_summary`: state clearly what is built/prepared vs which market pillars have NOT been started yet.
- Map all pillars into `scorecard` (`Done` / `Weak` / `Missing`) ranked 1..N.
- In `market_blind_spots_3`: max 3 non-obvious macro MARKET/BUSINESS blind spots with real sources or `Assumption`, plus a macro `strategic_consideration`.
- In `macro_bundles`: propose 3-4 clean **Macro Focus Bundles** (`main_aspect` + `keep_in_mind_alongside` 2-3 key factors) so the user selects macro directions before Cohort selection (`/obsi-priority`).
- In `private_unknown_questions_max_3`: max 3 crisp commercial questions (target customer, channel/budget, unit margin/pricing, partner offer). NEVER ask about personal bandwidth or other projects.
Call `finish` with valid JSON."""

    result = await agent(
        synth_prompt,
        schema=synthesis_schema,
        role="Macro Market Strategist",
        type_name="self",
        model="flash",
    )
    result = await enforce_no_code_output(result, synthesis_schema, "Macro Market Strategist")
    result["research_trace"] = research_trace
    log(f"100% Macro Market Scorecard ready for {project} (cache={research_trace['cache_status']}, pillars={len(result.get('scorecard', []))})")
    print(json.dumps(result, ensure_ascii=False, indent=2))

elif mode == "deep_dive":
    phase(f"Business Deep-Dive: {focus_pillar or 'Selected Pillar'}")

    deep_schema = {
        "type": "object",
        "properties": {
            "pillar": {"type": "string"},
            "diagnosis": {"type": "string"},
            "concrete_checklist": {"type": "array", "items": {"type": "string"}},
            "experiments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "metric": {"type": "string"},
                        "sample_size": {"type": "string"},
                        "kill_gate": {"type": "string"},
                        "effort_days": {"type": "number"},
                    },
                    "required": ["name", "metric", "sample_size", "kill_gate", "effort_days"],
                },
            },
            "next_3_actions": {"type": "array", "items": {"type": "string"}},
            "sources": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["pillar", "diagnosis", "concrete_checklist", "experiments", "next_3_actions", "sources"],
    }

    scorecards_abs = os.path.join(vault_path, scorecards_rel.replace("/", os.sep))
    sc_path = os.path.join(scorecards_abs, f"{project}.md")
    scorecard_context = existing_scorecard or (f"Read `{sc_path}` before advising." if os.path.exists(sc_path) else "")
    cache_res = (
        {"status": "MISS", "entry": None, "content": "", "matched_keywords": [], "age_days": None}
        if force_refresh
        else find_cached_playbook(playbooks_dir, f"{domain_model} {vision} {focus_pillar}", default_ttl=cache_ttl_days)
    )
    playbook_hint = (
        f"\nCached Market Playbook (`{cache_res['entry']['slug']}`, reuse before searching web):\n{cache_res['content']}\n"
        if cache_res["status"] == "HIT"
        else ""
    )

    deep_prompt = f"""{NO_CODE_RULE}
{VIBE_CODER_LENS}
Run a focused business/market Deep-Dive for '{project}' on pillar: '{focus_pillar}'.
Vision: {vision}
Scorecard context: {scorecard_context}
{playbook_hint}
1. Read `{sc_path}` if it exists for overall commercial alignment.
2. Reuse verified benchmarks/experiments from the Cached Playbook above first; ONLY run `search_web` if specific tactical details for '{focus_pillar}' are missing from cache.
3. Output plain, actionable guidance for a Vibe-Coder with concrete sample sizes, plain-language metrics, kill gates, and max 3 immediate market actions. Cite real URLs in `sources`. Call `finish` with valid JSON."""

    result = await agent(
        deep_prompt,
        schema=deep_schema,
        role=f"Market Deep-Dive Specialist: {focus_pillar}",
        type_name="self",
        model="flash",
    )
    result = await enforce_no_code_output(result, deep_schema, f"Market Deep-Dive Specialist: {focus_pillar}")
    result["research_trace"] = {
        "cache_status": cache_res["status"],
        "playbook_slug": cache_res["entry"]["slug"] if cache_res.get("entry") else "",
    }
    log(f"Business Deep-Dive completed for {project} :: {focus_pillar}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
else:
    raise ValueError(f"Unsupported mode: {mode!r}; expected 'full' or 'deep_dive'")
