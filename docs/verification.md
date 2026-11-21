# 🧪 Testing & Zero-Leakage Checks

**English** | [فارسی](fa/verification.md) · [← Back to README](../README.md)

All tests and deterministic checks live in [`tests/test_oss_plugin_suite.py`](../tests/test_oss_plugin_suite.py) and run on Linux, macOS, and Windows in CI ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)).

---

## 1. Run Locally

```bash
# Automated unit, E2E scaffolding, and zero-leakage suite (6 tests)
python -B tests/test_oss_plugin_suite.py -v

# Official Antigravity plugin manifest & skill validator
agy plugin validate . --strict

# Deterministic health audit against any Obsidian Vault
python -B skills/second-brain/scripts/vault_audit.py --vault /path/to/your/Vault --json
```

---

## 2. What the Automated Suite Verifies

1. **Plugin Manifest & Rules Hygiene (`test_plugin_json_and_plain_rules_agents`):**
   Verifies `plugin.json` contains only supported Antigravity fields and `rules/AGENTS.md` has plain Markdown with zero accidental YAML frontmatter.
2. **Skill Manifests & Prompt Budget (`test_all_skills_valid_under_budget_and_zero_stale_refs`):**
   Checks all 6 skills parse cleanly with `yaml.safe_load`, match `name == folder`, and stay strictly `<= 3,500 B` UTF-8.
3. **Zero Personal Leakage (`test_zero_personal_leakage_across_entire_repo`):**
   Walks every `.md`, `.py`, `.json`, `.yaml`, `.yml`, and `.txt` file across the repository so private user paths, personal domains, or server IPs never enter the open-source package.
4. **End-to-End Scaffolding & Routing (`test_scaffold_en_and_fa_audit_clean_hub_and_consult_menu`):**
   Scaffolds real temporary Vaults in both `en` (`Mon–Sun`) and `fa` (`Sat–Fri`), runs `git init`, validates 0 errors and 0 warnings with [`vault_audit.py`](../skills/second-brain/scripts/vault_audit.py), adds an incremental project (`--add-project`), and exercises all `resolve_obsi_hub.py` and `resolve_consult_menu.py` states (`new`, `in_progress`, `ready_for_cohorts`, `stale`, `pick_project`).
5. **No-Code Firewall, AST & Playbook Cache (`test_ast_no_local_imports_firewall_and_playbook_cache`):**
   Parses [`consult_audit.py`](../skills/obsi-consult/scripts/consult_audit.py) with `ast.PyCF_ALLOW_TOP_LEVEL_AWAIT`, ensures no sibling imports break `run_workflow` isolation, ensures network-enabled `agent(type_name="self")` is used, tests `BANNED_TECH_RE` catches code leaks while passing business copy, and verifies `playbook_cache.py` HIT/MISS/save roundtrips.
6. **Delta Transcript Recovery (`test_truncation_recovery_markers_delta_and_last_n`):**
   Verifies [`extract_session_steps.py`](../skills/second-brain/scripts/extract_session_steps.py) recovers truncated fields from `transcript_full.jsonl`, detects `/obsi-inspect` markers, and slices exact conversation deltas.
