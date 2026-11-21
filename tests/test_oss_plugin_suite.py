#!/usr/bin/env python3
"""
Comprehensive automated E2E & Zero-Leakage test suite for the obsi-founder-compass OSS plugin.
"""
import ast
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")

sys.path.insert(0, os.path.join(SKILLS_DIR, "second-brain", "scripts"))
import extract_session_steps as ess  # noqa: E402
import resolve_obsi_hub as roh  # noqa: E402
import vault_audit as va  # noqa: E402

sys.path.insert(0, os.path.join(SKILLS_DIR, "obsi-consult", "scripts"))
import playbook_cache as pc  # noqa: E402
import resolve_consult_menu as rcm  # noqa: E402

SETUP_SCRIPT = os.path.join(SKILLS_DIR, "obsi-setup", "scripts", "scaffold_brain.py")
CONSULT_SCRIPT = os.path.join(SKILLS_DIR, "obsi-consult", "scripts", "consult_audit.py")

ALLOWED_PLUGIN_FIELDS = {
    "name",
    "description",
    "logo",
    "suggestedPrompts",
    "displayName",
    "version",
    "author",
    "homepage",
    "repository",
    "disabled",
}

FORBIDDEN_PERSONAL_TOKENS = (
    "sher" + "vin",
    "mal" + "kadeh",
    "stl" + "cnc",
    "hal-o-" + "tamrin",
    "soumeh" + "sara",
    "d:\\projects\\" + "brain",
    "87.248." + "145.58",
    "to" + "rob",
    "zi" + "bal",
    "sa" + "dad",
    "c:\\users\\",
)


class TestPluginManifestAndZeroLeakage(unittest.TestCase):
    def test_plugin_json_and_plain_rules_agents(self):
        manifest_path = os.path.join(REPO_ROOT, "plugin.json")
        self.assertTrue(os.path.exists(manifest_path))
        data = json.loads(va._read_text(manifest_path))
        extra = set(data.keys()) - ALLOWED_PLUGIN_FIELDS
        self.assertEqual(extra, set(), f"Unsupported plugin.json top-level fields: {extra}")
        self.assertEqual(data.get("name"), "obsi-founder-compass")
        self.assertTrue(str(data.get("description") or "").strip())

        rules_path = os.path.join(REPO_ROOT, "rules", "AGENTS.md")
        self.assertTrue(os.path.exists(rules_path))
        rules_txt = va._read_text(rules_path)
        self.assertFalse(rules_txt.lstrip().startswith("---"), "Plugin rules/AGENTS.md must NOT have YAML frontmatter")

    def test_all_skills_valid_under_budget_and_zero_stale_refs(self):
        skill_paths = sorted(glob.glob(os.path.join(SKILLS_DIR, "*", "SKILL.md")))
        self.assertEqual(len(skill_paths), 6, f"Expected 6 skills, got {len(skill_paths)}")
        for sp in skill_paths:
            folder = os.path.basename(os.path.dirname(sp))
            raw = va._read_bytes(sp)
            self.assertLessEqual(len(raw), 3500, f"{folder}/SKILL.md exceeds 3500 B ({len(raw)} B)")
            fm, err = va.parse_frontmatter(raw.decode("utf-8"))
            self.assertIsNone(err, f"{folder}/SKILL.md YAML error: {err}")
            self.assertEqual(fm.get("name"), folder)
            self.assertTrue(str(fm.get("description") or "").strip())

    def test_zero_personal_leakage_across_entire_repo(self):
        hits = []
        for root, dirs, files in os.walk(REPO_ROOT):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".pytest_cache")]
            for fn in sorted(files):
                if not fn.endswith((".md", ".py", ".json", ".yaml", ".yml", ".txt")):
                    continue
                fp = os.path.join(root, fn)
                low = va._read_text(fp).lower()
                for tok in FORBIDDEN_PERSONAL_TOKENS:
                    if tok in low:
                        hits.append((os.path.relpath(fp, REPO_ROOT), tok))
        self.assertEqual(hits, [], f"Personal leakage detected: {hits}")


class TestEndToEndScaffoldingAndRouting(unittest.TestCase):
    def test_scaffold_en_and_fa_audit_clean_hub_and_consult_menu(self):
        for lang in ("en", "fa"):
            with tempfile.TemporaryDirectory() as tmp:
                vault_dir = os.path.join(tmp, f"brain_{lang}")
                app1 = os.path.join(tmp, "acme_saas")
                app2 = os.path.join(tmp, "creator_tool")
                os.makedirs(app1, exist_ok=True)
                os.makedirs(app2, exist_ok=True)
                cfg_path = os.path.join(tmp, "brain-os.json")

                proc = subprocess.run(
                    [
                        sys.executable,
                        SETUP_SCRIPT,
                        "--vault",
                        vault_dir,
                        "--lang",
                        lang,
                        "--pillars",
                        "Projects,Content,Self,Family",
                        "--projects",
                        f"AcmeSaaS|{app1}|Projects",
                        "--config-out",
                        cfg_path,
                        "--playbooks-dir",
                        os.path.join(SKILLS_DIR, "obsi-consult", "playbooks"),
                        "--git-init",
                        "--apply",
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertTrue(os.path.isdir(os.path.join(vault_dir, ".git")))

                audit = va.run_audit(vault_dir, SKILLS_DIR)
                self.assertEqual(audit["errors"], [], f"{lang} scaffold errors: {audit['errors']}")
                self.assertEqual(audit["warnings"], [], f"{lang} scaffold warnings: {audit['warnings']}")

                # Incremental --add-project
                proc2 = subprocess.run(
                    [
                        sys.executable,
                        SETUP_SCRIPT,
                        "--vault",
                        vault_dir,
                        "--add-project",
                        f"CreatorTool|{app2}|Content",
                        "--apply",
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                self.assertEqual(proc2.returncode, 0, proc2.stderr)
                self.assertEqual(va.run_audit(vault_dir, SKILLS_DIR)["errors"], [])

                # Add sample tasks for AcmeSaaS to verify one-line Hub task preview
                tasks_dir = os.path.join(vault_dir, "02-Tasks", "Projects", "AcmeSaaS")
                os.makedirs(tasks_dir, exist_ok=True)
                sample_tasks = {
                    "AcmeSaaS - Ship Landing.md": "status: Doing\ntoday: true\nday: Sun\npriority: High\naction: Publish landing page\n",
                    "AcmeSaaS - Call Leads.md": "status: Sprint\ntoday: false\nday: \"\"\npriority: Medium\naction: Reach out to five early beta leads and verify onboarding workflow bottlenecks cleanly\n",
                    "AcmeSaaS - Launch Ads.md": "status: Locked\ntoday: false\nday: \"\"\ndepends_on: \"[[AcmeSaaS - Ship Landing]]\"\npriority: Low\naction: Start paid campaign\n",
                    "AcmeSaaS - Setup Repo.md": "status: Done\ntoday: false\nday: \"\"\npriority: High\naction: Initialize codebase\n",
                }
                for fname, extra_yaml in sample_tasks.items():
                    with open(os.path.join(tasks_dir, fname), "w", encoding="utf-8") as f:
                        f.write(f"---\ntype: task\npillar: Projects\ncadence: finite\nproject: \"[[AcmeSaaS]]\"\n{extra_yaml}created: 2026-11-21\n---\n")

                # Hub checks
                hub_ready = roh.resolve_hub(cwd=app1, config_path=cfg_path)
                self.assertEqual(hub_ready["state"], "ready")
                self.assertEqual(hub_ready["detected_project"], "AcmeSaaS")
                self.assertEqual(len(hub_ready["recommended_options"]), 5)
                self.assertIn("Ship Landing", hub_ready["recommended_options"][0])
                self.assertEqual(hub_ready["project_tasks"]["active_total"], 2)
                self.assertEqual(hub_ready["project_tasks"]["locked_count"], 1)
                self.assertEqual(hub_ready["project_tasks"]["items"][0]["badge"], "🔥")
                self.assertEqual(hub_ready["project_tasks"]["items"][1]["badge"], "⚡")
                self.assertTrue(hub_ready["project_tasks"]["items"][1]["action"].endswith("bottlenecks…"))
                fa_cut = roh._truncate_words("تکمیل و ارسال نهایی درخواست درگاه پرداخت بانک ملی برای سایت فروشگاهی نمونه", 45)
                self.assertEqual(fa_cut, "تکمیل و ارسال نهایی درخواست درگاه پرداخت…")
                card = hub_ready["project_tasks_card"]
                self.assertIn("Ship Landing", card)
                self.assertIn("Call Leads", card)
                self.assertIn("1", card)
                self.assertNotIn("Setup Repo", card)

                hub_missing = roh.resolve_hub(cwd=app1, config_path=os.path.join(tmp, "none.json"))
                self.assertEqual(hub_missing["state"], "needs_setup")

                # Consult menu states
                self.assertEqual(rcm.resolve_menu(vault_dir, cwd=app1, lang=lang)["state"], "new")
                self.assertEqual(rcm.resolve_menu(vault_dir, cwd=r"C:\other\unmatched", lang=lang)["state"], "pick_project")

                today = datetime.date.today().isoformat()
                sc_file = os.path.join(vault_dir, "00-Focus", "Scorecards", "AcmeSaaS.md")
                with open(sc_file, "w", encoding="utf-8") as f:
                    f.write(
                        f"---\ntype: scorecard\nlast_full_audit: {today}\nactive_deep_dive: \"Ready for Cohort selection\"\n---\n"
                        "## 🎯 Macro Focus Bundles\n1. **ICP & First 10 Design Partners** — main aspect\n"
                    )
                ready_menu = rcm.resolve_menu(vault_dir, cwd=app1, lang=lang)
                self.assertEqual(ready_menu["state"], "ready_for_cohorts")
                self.assertEqual(ready_menu["bundles"], ["ICP & First 10 Design Partners"])

                with open(sc_file, "w", encoding="utf-8") as f:
                    f.write(
                        f"---\ntype: scorecard\nlast_full_audit: {today}\nactive_deep_dive: \"Refining Value Proposition\"\n---\n"
                    )
                self.assertEqual(rcm.resolve_menu(vault_dir, cwd=app1, lang=lang)["state"], "in_progress")

                with open(sc_file, "w", encoding="utf-8") as f:
                    f.write("---\ntype: scorecard\nlast_full_audit: 2020-01-01\n---\n")
                self.assertEqual(rcm.resolve_menu(vault_dir, cwd=app1, lang=lang)["state"], "stale")


class TestConsultWorkflowAndCache(unittest.TestCase):
    def test_ast_no_local_imports_firewall_and_playbook_cache(self):
        src = va._read_text(CONSULT_SCRIPT)
        tree = compile(src, CONSULT_SCRIPT, "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT | ast.PyCF_ONLY_AST)
        self.assertIsInstance(tree, ast.Module)
        self.assertNotIn("import playbook_cache", src)
        self.assertNotIn("from playbook_cache", src)
        for req in ["NO_CODE_RULE", "NO_CAPACITY_POLICING", "VIBE_CODER_LENS", "macro_bundles", "research_trace"]:
            self.assertIn(req, src)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "agent":
                for kw in node.keywords:
                    if kw.arg == "type_name" and isinstance(kw.value, ast.Constant):
                        self.assertNotEqual(kw.value.value, "research")

        assign_node = next(
            n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "BANNED_TECH_RE" for t in n.targets)
        )
        ns = {"re": re}
        exec(compile(ast.Module(body=[assign_node], type_ignores=[]), "<ast>", "exec"), ns)
        banned_re = ns["BANNED_TECH_RE"]
        self.assertIsNotNone(banned_re.search("Check routes/api and Core Web Vitals LCP in Order.php"))
        self.assertIsNone(banned_re.search("Acquire first 10 design partners and validate willingness to pay"))

        pb_dir = os.path.join(SKILLS_DIR, "obsi-consult", "playbooks")
        hit = pc.find_cached_playbook(pb_dir, "B2B SaaS MVP launch with free trial conversion", 90)
        self.assertEqual(hit["status"], "HIT")
        self.assertEqual(hit["entry"]["slug"], "b2b-saas-mvp-launch")
        self.assertEqual(pc.find_cached_playbook(pb_dir, "Local artisan bakery storefront", 90)["status"], "MISS")

        with tempfile.TemporaryDirectory() as tmp:
            body_f = os.path.join(tmp, "b.md")
            with open(body_f, "w", encoding="utf-8") as f:
                f.write("## Pillars\n1. Niche Positioning\n")
            pc.save_playbook(tmp, "bakery-local", "Local Bakery", ["bakery", "storefront", "local"], va._read_text(body_f), ["https://example.com"])
            self.assertEqual(pc.find_cached_playbook(tmp, "Local artisan bakery storefront", 90)["status"], "HIT")


class TestInspectorTranscriptExtractor(unittest.TestCase):
    def test_truncation_recovery_markers_delta_and_last_n(self):
        with tempfile.TemporaryDirectory() as tmp:
            cid = "oss-chat-01"
            log_dir = os.path.join(tmp, "brain", cid, ".system_generated", "logs")
            os.makedirs(log_dir, exist_ok=True)
            compact = [
                {"step_index": 1, "type": "USER_INPUT", "content": "<USER_REQUEST>/obsi-consult AcmeSaaS</USER_REQUEST>"},
                {"step_index": 2, "type": "PLANNER_RESPONSE", "content": "", "tool_calls": [{"name": "search_web", "args": {"query": "B2B SaaS onboarding benchmarks"}}]},
                {"step_index": 3, "type": "GENERIC", "source": "MODEL", "status": "DONE", "content": "Activation median is 30-36%"},
                {"step_index": 4, "type": "PLANNER_RESPONSE", "content": "Short...", "truncated_fields": ["content"]},
                {"step_index": 5, "type": "USER_INPUT", "content": "<USER_REQUEST>/obsi-inspect check claims</USER_REQUEST>"},
                {"step_index": 6, "type": "PLANNER_RESPONSE", "content": "Verified activation citation."},
                {"step_index": 7, "type": "USER_INPUT", "content": "<USER_REQUEST>/obsi-inspect</USER_REQUEST>"},
            ]
            full = [{"step_index": 4, "type": "PLANNER_RESPONSE", "content": "Full recovered executive summary with verified citation."}]
            with open(os.path.join(log_dir, "transcript.jsonl"), "w", encoding="utf-8") as f:
                for row in compact:
                    f.write(json.dumps(row) + "\n")
            with open(os.path.join(log_dir, "transcript_full.jsonl"), "w", encoding="utf-8") as f:
                for row in full:
                    f.write(json.dumps(row) + "\n")

            markers = ess.extract_session_steps(tmp, cid, only_markers=True)
            self.assertIn("[Step 1]", markers)
            self.assertIn("[Step 5]", markers)

            delta = ess.extract_session_steps(tmp, cid, since_last_inspect=True)
            self.assertNotIn("[Step 1]", delta)
            self.assertIn("[Step 5]", delta)
            self.assertIn("[Step 6] ASSISTANT:", delta)

            full_slice = ess.extract_session_steps(tmp, cid, start_step=1, end_step=4)
            self.assertIn("Full recovered executive summary", full_slice)
            self.assertIn("query=B2B SaaS onboarding benchmarks", full_slice)
            self.assertIn("[Step 3 RESULT]: Activation median is 30-36%", full_slice)


if __name__ == "__main__":
    unittest.main()
