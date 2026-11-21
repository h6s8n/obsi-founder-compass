<div dir="rtl">

# 🧠 معماری ۵لایه چطور کار می‌کند؟

[English](../how-it-works.md) | **فارسی** · [← بازگشت به README](../../README.fa.md)

قطب‌نمای بنیان‌گذار، Antigravity را به یک کاکپیت استراتژیک و اجرایی متصل به فایل‌های Markdown محلی و **Baseهای بومی ابسیدین** (`.base` + بورد درون‌متنی هر پروژه — بدون نیاز به هیچ پلاگین جانبی) تبدیل می‌کند.

مرجع اسکیما: [`skills/second-brain/SKILL.md`](../../skills/second-brain/SKILL.md) · چارچوب تصمیم: [`decision_frameworks.md`](../../skills/second-brain/references/decision_frameworks.md).

---

## ۱. پنج لایه ساختار Hub-and-Spoke

| لایه | دستور | وظیفه اصلی | گاردریل کلیدی |
| :---: | :--- | :--- | :--- |
| **۰** | `/obsi-setup` | ساخت والت، تقویم (`fa` شنبه–جمعه یا `en` دوشنبه–یکشنبه)، ستون‌ها و `brain-os.json` | پیش‌نمایش `--dry-run` + دست‌نزدن به نوت‌های قبلی |
| **۱** | `/obsi-consult` | تحلیل بازار، خریداران، قیمت‌گذاری، اعتماد و **بسته‌های تمرکز کلان (Macro Bundles)** | **آینه هدف** + **فایروال کد** + **ممنوعیت پلیسی زمان** |
| **۲** | `/obsi-priority` | تبدیل بسته‌های تمرکز به **کوهورت ۱۴روزه** و تسک‌های اتمیک | پیشنهاد حجم کار اختیاری و گیت‌های `ادامه / چرخش / توقف` |
| **۳** | `/obsi` | هاب کلیکی ۵ لایه (`resolve_obsi_hub.py`)، ثبت فوری، `/obsi next` و `/obsi done` | باز کردن خودکار تسک‌های قفل (`Locked` ← `Sprint`) |
| **۴** | `/obsi-inspect` | ممیزی چت برای شکار ادعای بدون منبع + چک ۱ثانیه‌ای سلامت والت | خواندن دلتای دقیق از `transcript.jsonl` با `extract_session_steps.py` |

---

## ۲. ساختار والت با Base بومی (SSOT)

اسکریپت [`scaffold_brain.py`](../../skills/obsi-setup/scripts/scaffold_brain.py) کل والت را طبق اصل منبع واحد حقیقت می‌سازد:

- **`00-Home.md`** — داشبورد زنده شامل `Today.base`، `Weekly.base` و `Cohorts.base` (بدون لیست دستی).
- **`Today.base` · `Weekly.base` · `Tasks.base`** — نمای زنده با فیلتر `status == "Sprint" || status == "Doing"`، بدون هاردکد کردن نام اسپرینت و همیشه با `null` داخل `groupOrder` کانبان.
- **`00-Focus/Cohorts/`** — آزمایش‌های زمان‌بندی‌شده ۱۴روزه با هدف عددی، متریک‌های پیشرو/پسرو و معیار ادامه/توقف.
- **`00-Focus/Scorecards/`** — حافظه زنده هر پروژه (`last_full_audit`، `active_deep_dive`) برای ادامه از محل توقف (Route B) بدون سرچ مجدد.
- **`01-Projects/`** — هاب مستقل هر پروژه با فیلدهای `type: project`، `pillar:`، `workspace:` و بورد کانبان اختصاصی.

---

## ۳. گاردریل‌های کلیدی در `/obsi-consult`

1. **آینه هدف (Vision Mirror Gate):** پیش از تحقیق عمیق، مشاور حداکثر ۴ سوال می‌پرسد، درک خود را در ۴ خط ساده بازتاب می‌دهد و تا تایید شما جلو نمی‌رود.
2. **کش پلی‌بوک (۹۰ روزه):** [`consult_audit.py`](../../skills/obsi-consult/scripts/consult_audit.py) پیش از جستجوی وب، [`playbooks/index.json`](../../skills/obsi-consult/playbooks/index.json) را چک می‌کند تا هزینه و زمان سرچ تکراری صفر شود.
3. **فایروال کد:** regex کنترلی `BANNED_TECH_RE` جلوی ورود بحث کدنویسی به مشاوره تجاری را می‌گیرد؛ وضعیت فنی فقط در یک جمله خلاصه می‌شود (*«زیرساخت محصول آماده است»*).
4. **بازشدن زنجیره‌ای تسک‌ها:** تسک‌ها می‌توانند `depends_on: "[[Blocker-Task]]"` و `status: Locked` داشته باشند تا به محض اجرای `/obsi done` روی تسک قبلی، خودکار به `Sprint` منتقل شوند.

</div>
