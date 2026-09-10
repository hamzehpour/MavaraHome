# خانه ماورا

سامانه‌ی رزرو بلیت و مدیریت محتوای مجموعه‌ی هنری **خانه ماورا** — یک ربات
تلگرام و یک وب‌سایت که روی **یک دیتابیس مشترک** کار می‌کنند: مخاطب از هر دو
مسیر بلیت رزرو می‌کند و ادمین از هر دو مسیر مدیریت می‌کند.

🌐 [mavarahome.com](https://mavarahome.com)

## 📚 مستندات

**از [`docs/README.md`](docs/README.md) شروع کنید** — آنجا بر اساس نقش شما
(توسعه‌دهنده، طراح، مدیر سرور، کارفرما) مسیر خواندن مشخص شده.

اگر توسعه‌دهنده‌اید یا از یک ابزار هوش مصنوعی استفاده می‌کنید، اول
[`AGENTS.md`](AGENTS.md) را بخوانید — قواعدی که شکستنشان سیستم را خراب می‌کند.

| | |
|---|---|
| [`AGENTS.md`](AGENTS.md) | قواعد کار روی این کد + تله‌های تکرارشونده |
| [`docs/01-product.md`](docs/01-product.md) | محصول، کاربران، واژه‌نامه‌ی دامنه، جریان پول |
| [`docs/02-architecture.md`](docs/02-architecture.md) | معماری و دلیل هر تصمیم فنی |
| [`docs/03-data-model.md`](docs/03-data-model.md) | جدول‌ها و **ماشین وضعیت رزرو** |
| [`docs/09-troubleshooting.md`](docs/09-troubleshooting.md) | عیب‌یابی: علامت ← علت ← راه‌حل |
| [`bot/DEPLOYMENT.md`](bot/DEPLOYMENT.md) | دیپلوی روی سرور |
| [`CHANGELOG.md`](CHANGELOG.md) | تاریخچه‌ی کامل هر تغییر، با دلیلش |

## ساختار

```
bot/        بک‌اند: ربات تلگرام + API + دیتابیس + منطق تجاری
website/    فرانت‌اند استاتیک: سایت عمومی + پنل ادمین
docs/       مستندات محصول و مهندسی
```

## راه‌اندازی محلی

```bash
cd bot
python3 -m venv venv && source venv/bin/activate   # ویندوز: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # BOT_TOKEN و JWT_SECRET را پر کنید
python3 migrate.py          # ساخت دیتابیس
python3 create_web_admin.py # ساخت حساب پنل ادمین

# سایت + API با هم، روی یک پورت:
STATIC_ROOT=../website python3 -m api.server
#   سایت:  http://127.0.0.1:8788
#   پنل:   http://127.0.0.1:8788/pages/admin/login.html

# ربات تلگرام (ترمینال جدا، نیاز به BOT_TOKEN واقعی):
python3 bot.py
```

## تست

```bash
cd bot && ENV=test python3 test_bot.py
```

هرگز به دیتابیس واقعی دست نمی‌زند. **قبل از هر کامیت باید ۱۰۰٪ سبز باشد.**

## پشته

Python 3.10+ · aiogram · `http.server` استاندارد (بدون فریمورک وب) · SQLite ·
HTML/CSS/JS ساده بدون build · فارسی و RTL به‌صورت درجه‌یک · تقویم جلالی

---

> نسخه‌ی قبلی این فایل یک راهنمای تست دستی «فاز ۴ تا ۸» بود که به دو صفحه‌ی
> حذف‌شده ارجاع می‌داد. آن متن در تاریخچه‌ی گیت باقی است؛ محتوای معتبر و
> به‌روز حالا در `docs/` است.
