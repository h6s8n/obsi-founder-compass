---
name: obsi-setup
kind: workflow
uses:
  - second-brain
description: "[Workflow] Layer 0 Obsidian Brain onboarding & structure manager (`/obsi-setup`): sets up a Native Bases Vault in 4 clickable questions via `scaffold_brain.py` or adds new projects/pillars safely. Silent in normal chat."
---

# `obsi-setup` — Layer 0 Setup & Structure Manager

Active **ONLY** on **`/obsi-setup`** (or when `/obsi` detects `needs_setup`). Dormant in normal engineering chat. **NEVER** write files before explicit user confirmation.

## 1. Fresh Onboarding Wizard (When Vault Is Missing)
Use [scaffold_brain.py](./scripts/scaffold_brain.py) after gathering 4–5 quick `ask_question` inputs:
1. Target Obsidian Vault path (e.g., `~/Obsidian/FounderBrain`).
2. Language & weekly calendar (`en` Mon–Sun vs `fa` Sat–Fri).
3. Life/work pillars (multi-select: `Projects`, `Content`, `Self`, `Family`, or custom).
4. Current project names + optional workspace directory paths (`Name|path`).

Then:
1. Run `python "<this-skill-dir>/scripts/scaffold_brain.py" --vault "<vault>" --lang <en|fa> --pillars "<list>" --projects "<specs>" --dry-run` to preview planned files.
2. Summarize planned structure in 2–3 lines and ask 1-line confirmation.
3. Run `--apply --git-init --config-out "<user-home>/.gemini/config/brain-os.json" --playbooks-dir "<sibling-obsi-consult-playbooks>"` (idempotent; skips existing notes), then invite the user into `/obsi-consult`.

## 2. Add Project / Pillar to Existing Vault
Run `scaffold_brain.py --vault "<vault>" --add-project "<Name>|<workspace>|<Pillar>" [--parent "<Umbrella>"] [--aliases "<a1,a2>"] --dry-run`, confirm in 1 line, apply with `--apply`, and offer `/obsi-consult <Name>`.

## 3. Multi-Project Workspace Subfolder Discovery
When `/obsi` or `/obsi-setup` runs inside a workspace with multiple/unregistered folders:
1. Run `python "<this-skill-dir>/scripts/scaffold_brain.py" --vault "<vault>" --scan-workspace "<cwd>"` (read-only).
2. Present `unregistered_subfolders` via `ask_question` (multi-select) so the user chooses which folders to register as separate projects now (or ignore for later).
3. Ask whether each selected folder should be standalone (`--add-project "Name|path|Pillar"`) or grouped under an existing umbrella (`--parent "<Umbrella>"`), optionally capturing `--aliases`.
4. Preview with `--dry-run`, confirm in 1 line, apply with `--apply`, and offer `/obsi-consult <Name>`.
