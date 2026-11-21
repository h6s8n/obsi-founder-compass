# 🧭 Commands, CLI Scripts & Config

**English** | [فارسی](fa/commands.md) · [← Back to README](../README.md)

Every interaction stays silent during regular coding until you invoke one of the 5 slash commands below.

---

## 1. Slash Command Reference

| Command | Mode | What it does |
| :--- | :--- | :--- |
| `/obsi` | Smart Hub + Layer 3 | Runs [`resolve_obsi_hub.py`](../skills/second-brain/scripts/resolve_obsi_hub.py), auto-detects your workspace project, and pops up the 5-layer menu (`ask_question`) |
| `obsi <text>` | Quick Capture | Classifies thought (Task, Idea, Project, Cohort), drafts YAML frontmatter, confirms in 1 line, writes cleanly |
| `/obsi next` | Daily Execution | Surfaces the single highest-priority unlocked active task ready now |
| `/obsi tactical` | Weekly Scheduling | Plans day slots (`Mon–Sun` or `Sat–Fri`) with half-line concrete `action:` steps |
| `/obsi done [task]` | Complete + Unlock | Marks `status: Done`, clears `today`, records `completed`, promotes matched `Locked` dependents to `Sprint` |
| `/obsi-setup` | Layer 0 Onboarding | Launches 4-question Vault wizard or adds a new project/pillar incrementally |
| `/obsi-consult` | Layer 1 Strategy | Runs [`resolve_consult_menu.py`](../skills/obsi-consult/scripts/resolve_consult_menu.py) (`new` / `in_progress` / `ready_for_cohorts` / `stale` / `pick_project`) |
| `/obsi-priority` | Layer 2 Cohorts | Turns approved Macro Focus Bundles into 14-day Cohorts & atomic tasks with advisory pacing |
| `/obsi-inspect` | Layer 4 Auditor | Audits delta turns from `transcript.jsonl` (`--since-last-inspect`) or runs `/obsi-inspect vault` |

---

## 2. Configuration File (`~/.gemini/config/brain-os.json`)

Generated automatically on setup (optional to edit manually):

```json
{
  "vault_path": "/path/to/your/Obsidian/FounderBrain",
  "playbooks_dir": "/path/to/playbooks",
  "language": "en",
  "calendar": "mon-sun",
  "scorecards_dir": "00-Focus/Scorecards",
  "decisions_dir": "00-Focus/Decisions",
  "cache_ttl_days": 90
}
```

---

## 3. Standalone CLI Scripts

```bash
# Preview a fresh Vault scaffold without writing to disk
python -B skills/obsi-setup/scripts/scaffold_brain.py \
  --vault ~/Obsidian/FounderBrain --lang en \
  --pillars "Projects,Content,Self,Family" \
  --projects "AcmeSaaS|/path/to/acme|Projects" --dry-run

# Add a project incrementally to an existing Vault
python -B skills/obsi-setup/scripts/scaffold_brain.py \
  --vault ~/Obsidian/FounderBrain \
  --add-project "CreatorTool|/path/to/tool|Content" --apply

# Check Hub / Consult smart-menu routing state
python -B skills/second-brain/scripts/resolve_obsi_hub.py --cwd /path/to/acme --json
python -B skills/obsi-consult/scripts/resolve_consult_menu.py --cwd /path/to/acme --json

# Query or store a 90-day Playbook entry
python -B skills/obsi-consult/scripts/playbook_cache.py lookup --query "B2B SaaS MVP launch" --json
```
