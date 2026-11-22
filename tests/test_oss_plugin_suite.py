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

sys.path.insert(0, os.path.join(REPO_ROOT, "mcp_server"))
import server as mcp_srv  # noqa: E402
import vault_engine as ve  # noqa: E402

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
                expected_opts = (
                    ["ایده خام", "مشاوره", "اولویت‌بندی", "کارهای امروز", "بازرسی"]
                    if lang == "fa"
                    else ["Raw Idea", "Consult", "Priority Plan", "Daily Tasks", "Audit"]
                )
                self.assertEqual(hub_ready["recommended_options"], expected_opts)
                for opt in hub_ready["recommended_options"]:
                    self.assertNotIn("Setup", opt)
                    self.assertNotIn("راه‌اندازی", opt)
                    self.assertNotIn("Layer", opt)
                    self.assertNotIn("لایه", opt)
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
                pick_all = rcm.resolve_menu(vault_dir, cwd=app1, lang=lang, pick_first=True)
                self.assertEqual(pick_all["state"], "pick_project")
                self.assertEqual([p["name"] for p in pick_all["projects"]], ["AcmeSaaS", "CreatorTool"])
                self.assertTrue(pick_all["recommended_options"][0].startswith("AcmeSaaS"))
                free_opt = "موضوع آزاد (بدون پروژه)" if lang == "fa" else "General Topic (no specific project)"
                self.assertIn(free_opt, pick_all["recommended_options"])

                picked_creator = rcm.resolve_menu(vault_dir, cwd=app1, explicit_project="CreatorTool", lang=lang)
                self.assertEqual(picked_creator["state"], "new")
                self.assertTrue(str(picked_creator.get("user_prompt") or "").strip())

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

    def test_multi_project_monorepo_disambiguation_aliases_and_subfolder_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_dir = os.path.join(tmp, "brain_mono")
            monorepo = os.path.join(tmp, "mono_hub")
            video_dir = os.path.join(monorepo, "video")
            news_dir = os.path.join(monorepo, "news")
            side_app_dir = os.path.join(monorepo, "side_app")
            docs_misc_dir = os.path.join(monorepo, "docs_misc")
            for d in (
                video_dir,
                news_dir,
                os.path.join(side_app_dir, ".git"),
                docs_misc_dir,
                os.path.join(monorepo, ".git"),
                os.path.join(monorepo, "node_modules"),
            ):
                os.makedirs(d, exist_ok=True)
            cfg_path = os.path.join(tmp, "brain-os.json")

            proc = subprocess.run(
                [
                    sys.executable,
                    SETUP_SCRIPT,
                    "--vault",
                    vault_dir,
                    "--lang",
                    "en",
                    "--pillars",
                    "Projects,Content",
                    "--projects",
                    f"Studio|{monorepo}|Content",
                    "--config-out",
                    cfg_path,
                    "--apply",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)

            for add_args in (
                ["--add-project", f"VideoChannel|{video_dir}|Content", "--parent", "Studio", "--aliases", "channel,vid"],
                ["--add-project", f"Newsletter|{news_dir}|Content", "--parent", "Studio"],
                ["--add-project", "ToolKit||Content", "--parent", "Studio"],
            ):
                p_add = subprocess.run(
                    [sys.executable, SETUP_SCRIPT, "--vault", vault_dir, *add_args, "--apply"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                self.assertEqual(p_add.returncode, 0, p_add.stderr)

            hub_mono = roh.resolve_hub(cwd=monorepo, config_path=cfg_path)
            self.assertEqual(hub_mono["state"], "ready")
            self.assertEqual(hub_mono["recommended_options"], ["Raw Idea", "Consult", "Priority Plan", "Daily Tasks", "Audit"])
            self.assertEqual(hub_mono["workspace_mode"], "multi_project")
            self.assertEqual(hub_mono["umbrella_project"], "Studio")
            ws_names = {p["name"] for p in hub_mono["workspace_projects"]}
            self.assertEqual(ws_names, {"Studio", "VideoChannel", "Newsletter", "ToolKit"})
            unreg_names = [u["name"] for u in hub_mono["unregistered_subfolders"]]
            self.assertEqual(unreg_names, ["side_app", "docs_misc"])
            self.assertTrue(hub_mono["unregistered_subfolders"][0]["is_git_repo"])
            self.assertIn("side_app (git)", hub_mono["project_tasks_card"])

            hub_alias = roh.resolve_hub(cwd=monorepo, config_path=cfg_path, explicit_project="channel")
            self.assertEqual(hub_alias["state"], "ready")
            self.assertEqual(hub_alias["detected_project"], "VideoChannel")

            hub_child = roh.resolve_hub(cwd=video_dir, config_path=cfg_path)
            self.assertEqual(hub_child["state"], "ready")
            self.assertEqual(hub_child["detected_project"], "VideoChannel")

            consult_mono = rcm.resolve_menu(vault_dir, cwd=monorepo, lang="en")
            self.assertEqual(consult_mono["state"], "pick_project")
            self.assertEqual(consult_mono["workspace_mode"], "multi_project")
            self.assertEqual([u["name"] for u in consult_mono["unregistered_subfolders"]], ["side_app", "docs_misc"])

            consult_alias = rcm.resolve_menu(vault_dir, cwd=monorepo, explicit_project="vid", lang="en")
            self.assertEqual(consult_alias["detected_project"], "VideoChannel")
            self.assertEqual(consult_alias["state"], "new")

            scan_proc = subprocess.run(
                [sys.executable, SETUP_SCRIPT, "--vault", vault_dir, "--scan-workspace", monorepo],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(scan_proc.returncode, 0, scan_proc.stderr)
            scan_data = json.loads(scan_proc.stdout)
            self.assertEqual([u["name"] for u in scan_data["unregistered_subfolders"]], ["side_app", "docs_misc"])

            reg_side = subprocess.run(
                [sys.executable, SETUP_SCRIPT, "--vault", vault_dir, "--add-project", f"SideApp|{side_app_dir}|Projects", "--apply"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(reg_side.returncode, 0, reg_side.stderr)

            hub_after = roh.resolve_hub(cwd=monorepo, config_path=cfg_path)
            self.assertEqual({p["name"] for p in hub_after["workspace_projects"]}, {"Studio", "VideoChannel", "Newsletter", "ToolKit", "SideApp"})
            self.assertEqual([u["name"] for u in hub_after["unregistered_subfolders"]], ["docs_misc"])

            clean_audit = va.run_audit(vault_dir, SKILLS_DIR)
            self.assertEqual(clean_audit["errors"], [], clean_audit["errors"])
            self.assertEqual(clean_audit["warnings"], [], clean_audit["warnings"])

            dup_proj = os.path.join(vault_dir, "01-Projects", "DuplicateWs.md")
            with open(dup_proj, "w", encoding="utf-8") as f:
                f.write(f"---\ntype: project\nstatus: active\npillar: Projects\nworkspace: \"{side_app_dir.replace(chr(92), chr(92)*2)}\"\nupdated: 2026-11-21\n---\n# DuplicateWs\n```base\nviews:\n  - type: table\n    name: T\n```\n")
            dup_audit = va.run_audit(vault_dir, SKILLS_DIR)
            self.assertTrue(any("Duplicate workspace path" in w for w in dup_audit["warnings"]), dup_audit["warnings"])


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

    def test_in_flight_consult_topic_detection_and_dynamic_option_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_dir = os.path.join(tmp, "brain_in_flight")
            app_dir = os.path.join(tmp, "app_dir")
            os.makedirs(app_dir, exist_ok=True)

            proc = subprocess.run(
                [
                    sys.executable,
                    SETUP_SCRIPT,
                    "--vault",
                    vault_dir,
                    "--lang",
                    "fa",
                    "--add-project",
                    f"TestApp|{app_dir}|Projects",
                    "--apply",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)

            sc_dir = os.path.join(vault_dir, "00-Focus", "Scorecards")
            os.makedirs(sc_dir, exist_ok=True)
            sc_file = os.path.join(sc_dir, "TestApp.md")
            with open(sc_file, "w", encoding="utf-8") as f:
                f.write(
                    "---\n"
                    "type: scorecard\n"
                    "last_full_audit: 2026-11-21\n"
                    "active_deep_dive: \"فاز ۱ بسته شد — توافق ثبت شد\"\n"
                    "---\n"
                    "## 🎯 محورهای کلان انتخابی\n"
                    "1. **محور ۱ — تست اولیه**\n"
                )

            # 1. When all topics are closed, Option 1 is standard
            menu1 = rcm.resolve_menu(vault_dir, cwd=app_dir, lang="fa")
            self.assertIsNone(menu1.get("pending_topic"))
            self.assertIn("اضافه کردن بحث یا تصمیم کلان جدید", menu1["recommended_options"][0])
            self.assertIn("حرفت", menu1.get("user_prompt") or "")

            # 2. When a draft decision exists in 00-Focus/Decisions/
            decisions_dir = os.path.join(vault_dir, "00-Focus", "Decisions")
            os.makedirs(decisions_dir, exist_ok=True)
            draft_decision_file = os.path.join(decisions_dir, "2026-11-21 - TestApp Partner RevShare Agreement.md")
            with open(draft_decision_file, "w", encoding="utf-8") as f:
                f.write(
                    "---\n"
                    "type: decision\n"
                    "project: \"[[TestApp]]\"\n"
                    "title: \"قرارداد شراکت نریشن و تقسیم سود\"\n"
                    "status: draft\n"
                    "---\n"
                    "# صورت‌جلسه پیش‌نویس\n"
                )

            menu2 = rcm.resolve_menu(vault_dir, cwd=app_dir, lang="fa")
            self.assertIsNotNone(menu2.get("pending_topic"))
            self.assertEqual(menu2["pending_topic"]["title"], "قرارداد شراکت نریشن و تقسیم سود")
            self.assertEqual(menu2["pending_topic"]["source"], "decision_draft")
            self.assertIn("نهایی‌سازی و ثبت رسمی موضوع در جریان", menu2["recommended_options"][0])
            self.assertIn("قرارداد شراکت نریشن و تقسیم سود", menu2["recommended_options"][0])
            self.assertIn("موضوع معلق در جریان", menu2["summary_2lines"])

            # Verify English translation
            menu2_en = rcm.resolve_menu(vault_dir, cwd=app_dir, lang="en")
            self.assertIn("Finalize and record in-flight topic", menu2_en["recommended_options"][0])
            self.assertIn("In-flight topic pending closure", menu2_en["summary_2lines"])

            # 3. Simulate closure by updating status to Approved
            with open(draft_decision_file, "w", encoding="utf-8") as f:
                f.write(
                    "---\n"
                    "type: decision\n"
                    "project: \"[[TestApp]]\"\n"
                    "title: \"قرارداد شراکت نریشن و تقسیم سود\"\n"
                    "status: Approved\n"
                    "---\n"
                    "# صورت‌جلسه مصوب\n"
                )

            menu3 = rcm.resolve_menu(vault_dir, cwd=app_dir, lang="fa")
            self.assertIsNone(menu3.get("pending_topic"))
            self.assertIn("اضافه کردن بحث یا تصمیم کلان جدید", menu3["recommended_options"][0])

            # 4. Open active_deep_dive in Scorecard without draft file
            with open(sc_file, "w", encoding="utf-8") as f:
                f.write(
                    "---\n"
                    "type: scorecard\n"
                    "last_full_audit: 2026-11-21\n"
                    "active_deep_dive: \"بررسی استراتژی قیمت‌گذاری B2B\"\n"
                    "---\n"
                    "## 🎯 محورهای کلان انتخابی\n"
                    "1. **محور ۱ — تست اولیه**\n"
                )

            menu4 = rcm.resolve_menu(vault_dir, cwd=app_dir, lang="fa")
            self.assertIsNotNone(menu4.get("pending_topic"))
            self.assertEqual(menu4["pending_topic"]["source"], "scorecard_deep_dive")
            self.assertEqual(menu4["pending_topic"]["title"], "بررسی استراتژی قیمت‌گذاری B2B")
            self.assertIn("بررسی استراتژی قیمت‌گذاری B2B", menu4["recommended_options"][0])


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


class TestObsiMcpServerAndBaseEngine(unittest.TestCase):
    def test_mcp_config_manifest_and_vault_engine_base_driven_zero_hardcode(self):
        mcp_cfg_path = os.path.join(REPO_ROOT, "mcp_config.json")
        self.assertTrue(os.path.exists(mcp_cfg_path), "mcp_config.json must exist")
        cfg = json.loads(va._read_text(mcp_cfg_path))
        servers = cfg.get("mcpServers") or {}
        self.assertIn("obsi", servers)
        obsi_srv = servers["obsi"]
        self.assertIn("${PLUGIN_ROOT}/mcp_server/server.py", obsi_srv.get("args") or [])

        with tempfile.TemporaryDirectory() as tmp:
            vault_dir = os.path.join(tmp, "brain_mcp")
            app1 = os.path.join(tmp, "acme_app")
            os.makedirs(app1, exist_ok=True)
            cfg_path = os.path.join(tmp, "brain-os.json")

            proc = subprocess.run(
                [
                    sys.executable,
                    SETUP_SCRIPT,
                    "--vault",
                    vault_dir,
                    "--lang",
                    "en",
                    "--pillars",
                    "Projects,Content,Research",
                    "--projects",
                    f"AcmeApp|{app1}|Projects",
                    "--config-out",
                    cfg_path,
                    "--apply",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)

            p_add = subprocess.run(
                [
                    sys.executable,
                    SETUP_SCRIPT,
                    "--vault",
                    vault_dir,
                    "--add-project",
                    "AcmeWeb||Projects",
                    "--parent",
                    "AcmeApp",
                    "--aliases",
                    "acme,portal",
                    "--apply",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(p_add.returncode, 0, p_add.stderr)

            tasks_dir = os.path.join(vault_dir, "02-Tasks", "Projects", "AcmeApp")
            web_dir = os.path.join(vault_dir, "02-Tasks", "Projects", "AcmeWeb")
            research_dir = os.path.join(vault_dir, "02-Tasks", "Research")
            os.makedirs(tasks_dir, exist_ok=True)
            os.makedirs(web_dir, exist_ok=True)
            os.makedirs(research_dir, exist_ok=True)

            t1_body = "\n# Blocker Task\n\n## Checklist\n- [ ] Ship pricing\n"
            with open(os.path.join(tasks_dir, "AcmeApp - Ship Pricing.md"), "w", encoding="utf-8") as f:
                f.write(
                    "---\n"
                    "type: task\n"
                    "pillar: Projects\n"
                    "cadence: finite\n"
                    'project: "[[AcmeApp]]"\n'
                    "status: Doing\n"
                    "today: true\n"
                    "day: Mon\n"
                    "priority: High\n"
                    'action: "Publish pricing page"\n'
                    "created: 2026-11-22\n"
                    "---"
                    + t1_body
                )
            with open(os.path.join(web_dir, "AcmeWeb - Fix SEO.md"), "w", encoding="utf-8") as f:
                f.write(
                    "---\n"
                    "type: task\n"
                    "pillar: Projects\n"
                    "cadence: finite\n"
                    'project: "[[AcmeWeb]]"\n'
                    "status: Sprint\n"
                    "today: false\n"
                    "priority: Medium\n"
                    'action: "Add meta tags"\n'
                    "---\n"
                )
            with open(os.path.join(tasks_dir, "AcmeApp - Announce Launch.md"), "w", encoding="utf-8") as f:
                f.write(
                    "---\n"
                    "type: task\n"
                    "pillar: Projects\n"
                    "cadence: finite\n"
                    'project: "[[AcmeApp]]"\n'
                    "status: Locked\n"
                    "today: false\n"
                    'depends_on: "[[AcmeApp - Ship Pricing]]"\n'
                    "priority: High\n"
                    'action: "Post launch thread"\n'
                    "---\n# Launch\n"
                )
            # Brand-new custom pillar & status to prove zero hardcoding
            with open(os.path.join(research_dir, "Lab - Paper Review.md"), "w", encoding="utf-8") as f:
                f.write(
                    "---\n"
                    "type: task\n"
                    "pillar: Research\n"
                    "cadence: finite\n"
                    'project: "[[ResearchLab]]"\n'
                    "status: Review\n"
                    "today: false\n"
                    "priority: High\n"
                    'action: "Evaluate benchmark paper"\n'
                    "---\n"
                )
            custom_base_path = os.path.join(vault_dir, "ResearchQueue.base")
            with open(custom_base_path, "w", encoding="utf-8") as f:
                f.write(
                    "filters:\n"
                    "  and:\n"
                    '    - file.inFolder("02-Tasks")\n'
                    '    - pillar == "Research"\n'
                    "properties:\n"
                    "  action:\n"
                    "    displayName: Research Step\n"
                    "views:\n"
                    "  - type: kanban\n"
                    "    name: Custom Review Queue\n"
                    "    filters:\n"
                    "      and:\n"
                    '        - status == "Review"\n'
                    "    groupBy:\n"
                    "      property: status\n"
                    "      direction: ASC\n"
                    "    groupOrder:\n"
                    "      - Review\n"
                    "      - null\n"
                    "    order:\n"
                    "      - file.name\n"
                    "      - action\n"
                )

            # 1. Dynamic base discovery & custom base execution
            bases_cat = ve.list_bases_summary(vault_dir)
            base_names = {b["name"] for b in bases_cat["bases"]}
            self.assertTrue({"Tasks", "Today", "Weekly", "Cohorts", "Projects", "ResearchQueue"} <= base_names)

            q_custom = ve.query_base(vault_dir, base="ResearchQueue.base")
            self.assertEqual(q_custom["view"], "Custom Review Queue")
            self.assertEqual(q_custom["total_matched"], 1)
            self.assertEqual(q_custom["items"][0]["file_name"], "Lab - Paper Review")
            self.assertEqual(q_custom["items"][0]["status"], "Review")

            q_today = ve.query_base(vault_dir, base="Today.base")
            self.assertEqual(q_today["total_matched"], 1)
            self.assertEqual(q_today["items"][0]["file_name"], "AcmeApp - Ship Pricing")

            # 2. Cross-project list_tasks with alias & limit
            lt_all = ve.list_tasks(vault_dir, limit=2)
            self.assertEqual(lt_all["returned_count"], 2)
            self.assertEqual(lt_all["counts"]["today"], 1)
            self.assertEqual(lt_all["counts"]["locked"], 1)
            self.assertTrue(lt_all["truncated"])
            self.assertEqual(lt_all["items"][0]["file_name"], "AcmeApp - Ship Pricing")

            lt_alias = ve.list_tasks(vault_dir, project="portal")
            self.assertEqual([i["file_name"] for i in lt_alias["items"]], ["AcmeWeb - Fix SEO"])

            lt_umbrella = ve.list_tasks(vault_dir, project="AcmeApp")
            self.assertEqual(
                {i["file_name"] for i in lt_umbrella["items"]},
                {"AcmeApp - Ship Pricing", "AcmeWeb - Fix SEO"},
            )

            # 3. Path traversal rejection & safe mutation + cascading unlock
            with self.assertRaises(ValueError):
                ve.update_task(vault_dir, "../00-Home.md", status="Done")

            upd = ve.update_task(vault_dir, "AcmeApp - Ship Pricing", status="Done")
            self.assertEqual(upd["task"]["status"], "Done")
            self.assertFalse(upd["task"]["today"])
            self.assertEqual(upd["completed"], datetime.date.today().isoformat())
            self.assertEqual([u["file_name"] for u in upd["unlocked_tasks"]], ["AcmeApp - Announce Launch"])

            with open(os.path.join(tasks_dir, "AcmeApp - Ship Pricing.md"), "r", encoding="utf-8") as f:
                saved_txt = f.read()
            self.assertTrue(saved_txt.endswith(t1_body), "Markdown body must stay preserved byte-for-byte")

            # 4. Real subprocess Stdio JSON-RPC 2.0 E2E check
            reqs = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "ping"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "list_bases", "arguments": {}}},
                {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "list_tasks", "arguments": {"limit": 10}}},
                {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "query_base", "arguments": {"base": "ResearchQueue.base"}}},
                {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "get_vault_overview", "arguments": {"cwd": app1}}},
                {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "update_task", "arguments": {"task_ref": "AcmeApp - Announce Launch", "status": "Doing", "today": True}}},
                {"jsonrpc": "2.0", "id": 9, "method": "resources/list"},
                {"jsonrpc": "2.0", "id": 10, "method": "resources/read", "params": {"uri": "obsi://overview"}},
                {"jsonrpc": "2.0", "id": 11, "method": "resources/read", "params": {"uri": "obsi://base/Today.base"}},
            ]
            stdin_payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in reqs) + "\n"
            env = dict(os.environ)
            env["OBSI_CONFIG_PATH"] = cfg_path
            env.pop("OBSI_VAULT_PATH", None)

            srv_proc = subprocess.run(
                [sys.executable, "-X", "utf8", os.path.join(REPO_ROOT, "mcp_server", "server.py")],
                input=stdin_payload,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            self.assertEqual(srv_proc.returncode, 0, srv_proc.stderr)
            self.assertEqual(srv_proc.stderr.strip(), "", f"Unexpected stderr: {srv_proc.stderr}")

            resps = [json.loads(line) for line in srv_proc.stdout.strip().splitlines()]
            self.assertEqual(len(resps), 11, "Notifications must not emit responses")
            by_id = {r["id"]: r["result"] for r in resps}

            self.assertEqual(by_id[1]["serverInfo"]["name"], "obsi-founder-compass")
            self.assertEqual(by_id[2], {})
            tool_names = [t["name"] for t in by_id[3]["tools"]]
            self.assertEqual(tool_names, ["list_tasks", "query_base", "list_bases", "get_vault_overview", "update_task"])
            self.assertFalse(by_id[4]["isError"])
            self.assertEqual(by_id[5]["structuredContent"]["items"][0]["file_name"], "AcmeApp - Announce Launch")
            self.assertEqual(by_id[6]["structuredContent"]["items"][0]["status"], "Review")
            self.assertEqual(by_id[7]["structuredContent"]["umbrella_project"], "AcmeApp")
            self.assertEqual(by_id[7]["structuredContent"]["workspace_mode"], "multi_project")
            self.assertEqual(by_id[8]["structuredContent"]["task"]["status"], "Doing")
            self.assertTrue(by_id[8]["structuredContent"]["task"]["today"])

            res_uris = {r["uri"] for r in by_id[9]["resources"]}
            self.assertIn("obsi://overview", res_uris)
            self.assertIn("obsi://base/ResearchQueue.base", res_uris)

            ov_json = json.loads(by_id[10]["contents"][0]["text"])
            self.assertGreaterEqual(ov_json["task_counts"]["today"], 1)
            today_json = json.loads(by_id[11]["contents"][0]["text"])
            self.assertEqual(today_json["items"][0]["file_name"], "AcmeApp - Announce Launch")


if __name__ == "__main__":
    unittest.main()
