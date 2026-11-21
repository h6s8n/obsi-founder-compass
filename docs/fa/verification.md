<div dir="rtl">

# 🧪 تست‌ها و جلوگیری از نشت اطلاعات

[English](../verification.md) | **فارسی** · [← بازگشت به README](../../README.fa.md)

تمام تست‌های خودکار در فایل [`tests/test_oss_plugin_suite.py`](../../tests/test_oss_plugin_suite.py) قرار دارند و در CI روی لینوکس، مک و ویندوز اجرا می‌شوند ([`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)).

---

## ۱. اجرای تست‌ها روی سیستم

</div>

```bash
# اجرای ۶ تست جامع واحد، اسکفولد E2E و ضد-نشت اطلاعات
python -B tests/test_oss_plugin_suite.py -v

# اعتبارسنج رسمی پلاگین در Antigravity CLI
agy plugin validate . --strict

# ممیزی قطعی سلامت یک والت دلخواه ابسیدین
python -B skills/second-brain/scripts/vault_audit.py --vault /path/to/your/Vault --json
```

<div dir="rtl">

---

## ۲. این تست‌ها چه مواردی را تضمین می‌کنند؟

1. **سلامت مانیفست و قوانین (`test_plugin_json_and_plain_rules_agents`):** چک می‌کند `plugin.json` فقط کلیدهای رسمی را دارد و `rules/AGENTS.md` بدون هدر YAML اضافی است.
2. **اعتبار اسکیل‌ها و سقف حجم (`test_all_skills_valid_under_budget_and_zero_stale_refs`):** تمام ۶ فایل `SKILL.md` را با `yaml.safe_load` چک می‌کند و مطمئن می‌شود حجم هر کدام `<= 3,500 B` باشد.
3. **جلوگیری کامل از نشت اطلاعات شخصی (`test_zero_personal_leakage_across_entire_repo`):** کل فایل‌های `.md`، `.py`، `.json`، `.yaml` و `.txt` را اسکن می‌کند تا هیچ مسیر محلی یا داده خصوصی وارد نسخه عمومی نشود.
4. **تست واقعی اسکفولد و روتینگ (`test_scaffold_en_and_fa_audit_clean_hub_and_consult_menu`):** هم به زبان انگلیسی (`Mon–Sun`) و هم فارسی (`Sat–Fri`) والت واقعی می‌سازد، با [`vault_audit.py`](../../skills/second-brain/scripts/vault_audit.py) صفر خطا تایید می‌کند، پروژه جدید می‌افزاید و تمام حالت‌های منوی هوشمند را تست می‌کند.
5. **فایروال کد و کش پلی‌بوک (`test_ast_no_local_imports_firewall_and_playbook_cache`):** فایل [`consult_audit.py`](../../skills/obsi-consult/scripts/consult_audit.py) را با AST پایتون چک می‌کند که ایمپورت لوکال نداشته باشد، `BANNED_TECH_RE` متن‌های فنی را بگیرد و کش `playbook_cache.py` درست کار کند.
6. **بازیابی ترنسکریپت برای بازرس (`test_truncation_recovery_markers_delta_and_last_n`):** مطمئن می‌شود [`extract_session_steps.py`](../../skills/second-brain/scripts/extract_session_steps.py) متن‌های بریده‌شده را از `transcript_full.jsonl` برمی‌گرداند و دلتای دقیق چت را برش می‌زند.

</div>
