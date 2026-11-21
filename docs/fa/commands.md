<div dir="rtl">

# 🧭 راهنمای دستورها، اسکریپت‌ها و تنظیمات

[English](../commands.md) | **فارسی** · [← بازگشت به README](../../README.fa.md)

تمام قوانین مشاوره و بازرسی در چت‌های عادی برنامه‌نویسی غیرفعال هستند و فقط با زدن یکی از دستورهای زیر فعال می‌شوند.

---

## ۱. مرجع اسلش‌کامندها

| دستور | لایه / حالت | عملکرد |
| :--- | :--- | :--- |
| `/obsi` | هاب هوشمند + لایه ۳ | با [`resolve_obsi_hub.py`](../../skills/second-brain/scripts/resolve_obsi_hub.py) پروژه فعلی را می‌شناسد و منوی ۵ لایه می‌آورد |
| `obsi <متن>` | ثبت فوری | نوع یادداشت (تسک، ایده، پروژه، کوهورت) را تشخیص داده و با تایید ۱خطی ذخیره می‌کند |
| `/obsi next` | اجرای روزانه | مهم‌ترین تسک باز (بدون قفل) آماده انجام همین الان را نشان می‌دهد |
| `/obsi tactical` | برنامه‌ریزی هفتگی | چیدمان روزهای هفته (`Sat–Fri` یا `Mon–Sun`) با `action:` مشخص |
| `/obsi done [task]` | تکمیل + بازگشایی | `status: Done` را ثبت و تسک‌های وابسته (`Locked`) را خودکار به `Sprint` منتقل می‌کند |
| `/obsi-setup` | لایه ۰ راه‌اندازی | ویزارد ۴ سوالی ساخت والت یا افزودن پروژه و ستون جدید |
| `/obsi-consult` | لایه ۱ مشاوره | با [`resolve_consult_menu.py`](../../skills/obsi-consult/scripts/resolve_consult_menu.py) وضعیت اسکورکارد (`new` / `in_progress` / `ready_for_cohorts` / `stale`) را می‌آورد |
| `/obsi-priority` | لایه ۲ کوهورت‌ها | بسته‌های تمرکز را با گزینه‌های پیشنهادی حجم کار به کوهورت ۱۴روزه تبدیل می‌کند |
| `/obsi-inspect` | لایه ۴ بازرسی | ممیزی دلتای چت (`--since-last-inspect`) یا چک کامل سلامت والت (`/obsi-inspect vault`) |

---

## ۲. فایل تنظیمات (`~/.gemini/config/brain-os.json`)

هنگام راه‌اندازی به‌صورت خودکار ساخته می‌شود:

</div>

```json
{
  "vault_path": "/path/to/your/Obsidian/FounderBrain",
  "playbooks_dir": "/path/to/playbooks",
  "language": "fa",
  "calendar": "sat-fri",
  "scorecards_dir": "00-Focus/Scorecards",
  "decisions_dir": "00-Focus/Decisions",
  "cache_ttl_days": 90
}
```

<div dir="rtl">

---

## ۳. اجرای مستقیم اسکریپت‌ها در ترمینال

</div>

```bash
# پیش‌نمایش ساخت والت بدون تغییر فایل روی دیسک
python -B skills/obsi-setup/scripts/scaffold_brain.py \
  --vault ~/Obsidian/FounderBrain --lang fa \
  --pillars "Projects,Content,Self,Family" \
  --projects "AcmeSaaS|/path/to/acme|Projects" --dry-run

# افزودن پروژه جدید به والت موجود
python -B skills/obsi-setup/scripts/scaffold_brain.py \
  --vault ~/Obsidian/FounderBrain \
  --add-project "CreatorTool|/path/to/tool|Content" --apply

# بررسی خروجی JSON هاب و منوی مشاور
python -B skills/second-brain/scripts/resolve_obsi_hub.py --cwd /path/to/acme --json
python -B skills/obsi-consult/scripts/resolve_consult_menu.py --cwd /path/to/acme --json
```
