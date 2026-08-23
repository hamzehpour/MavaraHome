# راهنمای استقرار (Deployment) — Mavara Home

این سند دقیقاً می‌گوید چطور بات تلگرام، بک‌اند یکپارچه (API)، و سایت را روی
یک VPS واقعی (Ubuntu) مستقر کنید — به‌گونه‌ای که هر سه به یک دیتابیس مشترک
وصل باشند (طبق معماری فاز ۱).

## معماری نهایی روی سرور

```
اینترنت
   │
   ▼
Nginx (پورت ۴۴۳، HTTPS)
   │
   ├── فایل‌های استاتیک سایت (index.html, pages/, assets/) — مستقیم از دیسک
   │
   └── /api/v1/*  و  /media/*  →  proxy →  Mavara API (پورت 8788، فقط داخلی)
                                        │
                                        ▼
                                   دیتابیس مشترک (SQLite)
                                        ▲
                                        │
                              بات تلگرام (پروسه جدا، همان دیتابیس)
```

هر سه (سایت، پنل ادمین، بات) به همان یک فایل SQLite وصل می‌شوند — دقیقاً
همان چیزی که در فاز ۱ ساخته و تست شد.

---

## ۱. پیش‌نیاز روی سرور

```bash
sudo apt update && sudo apt install -y python3 python3-venv nginx certbot python3-certbot-nginx
sudo useradd -r -s /bin/false mavara
```

## ۲. کپی کردن پروژه‌ها

```bash
sudo mkdir -p /opt/mavara-bot /opt/mavara-home-website
# فایل زیپ بات را روی سرور آپلود و در /opt/mavara-bot استخراج کنید
# فایل زیپ سایت را روی سرور آپلود و در /opt/mavara-home-website استخراج کنید
sudo chown -R mavara:mavara /opt/mavara-bot /opt/mavara-home-website
```

## ۳. نصب و پیکربندی بات + API

```bash
cd /opt/mavara-bot
sudo -u mavara python3 -m venv venv
sudo -u mavara venv/bin/pip install -r requirements.txt

sudo -u mavara cp .env.example .env
sudo -u mavara nano .env
# پر کنید:
#   BOT_TOKEN=<توکن واقعی از BotFather>
#   BOOTSTRAP_ADMIN_IDS=<آیدی عددی تلگرام خودتان>
#   ENV=production
#   API_ADMIN_TOKEN=<یک رمز طولانی و تصادفی — پیش‌فرض 1234 را عوض کنید>
#   JWT_SECRET=<یک رشته‌ی طولانی و تصادفی — با دستور زیر بسازید>
#     python3 -c "import secrets; print(secrets.token_hex(32))"

sudo -u mavara venv/bin/python migrate.py
sudo -u mavara venv/bin/python health_check.py   # باید 11/11 بدهد

# ساخت حساب ادمین سایت (Phase 2 — ورود واقعی با نام کاربری/رمز):
sudo -u mavara venv/bin/python create_web_admin.py
# نام کاربری و رمز عبور (حداقل ۱۰ کاراکتر) را وارد کنید — این‌ها همان
# اطلاعاتی هستند که در pages/admin/login.html سایت وارد می‌شوند.

# اگر می‌خواهید محتوای رزومه (۳۱ اثر) هم از همین اول موجود باشد:
sudo -u mavara venv/bin/python seed_portfolio.py

# هرگز روی production این را اجرا نکنید:
# seed_database.py   ← فقط برای ENV=test
```

## ۴. راه‌اندازی به‌عنوان سرویس (systemd)

```bash
sudo cp deploy/mavara-bot.service /etc/systemd/system/
sudo cp deploy/mavara-api.service /etc/systemd/system/
sudo nano /etc/systemd/system/mavara-bot.service   # مسیرها را با /opt/mavara-bot تطبیق دهید
sudo nano /etc/systemd/system/mavara-api.service

sudo systemctl daemon-reload
sudo systemctl enable --now mavara-bot
sudo systemctl enable --now mavara-api

# بررسی وضعیت:
sudo systemctl status mavara-bot
sudo systemctl status mavara-api
sudo journalctl -u mavara-api -f   # لاگ زنده
```

## ۵. تنظیم Nginx (سرو سایت + پروکسی API)

```bash
sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/mavara-home
sudo nano /etc/nginx/sites-available/mavara-home
# دامنه (server_name) و مسیر root را با دامنه/مسیر واقعی خودتان جایگزین کنید

sudo ln -s /etc/nginx/sites-available/mavara-home /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# گواهی HTTPS واقعی (اجباری — رمز ادمین و رسیدها هرگز نباید بدون رمزنگاری منتقل شوند):
sudo certbot --nginx -d mavara-home.example.com
```

## ۶. تست نهایی روی سرور واقعی

```bash
curl https://mavara-home.example.com/api/v1/events
# باید JSON رویدادها را برگرداند

curl https://mavara-home.example.com/
# باید index.html سایت را برگرداند
```

سپس در مرورگر واقعی:
1. سایت را باز کنید، یک رزرو واقعی ثبت کنید.
2. همان لحظه در بات تلگرام (که به همان دیتابیس وصل است) با `/admin` بررسی کنید که آن رزرو آنجا هم دیده می‌شود.
3. از پنل ادمین سایت (`/pages/admin/`) یک رویداد جدید بسازید و آن را «فعال» کنید — باید بلافاصله (بدون ری‌استارت بات) در لیست رویدادهای بات هم ظاهر شود.

---

## به‌روزرسانی نسخه‌ی جدید (بدون از دست دادن داده)

```bash
# بات:
cd /opt/mavara-bot
sudo systemctl stop mavara-bot mavara-api
# فایل‌های کد را جایگزین کنید (data/ و .env را دست نزنید — دیتای واقعی آنجاست)
sudo -u mavara venv/bin/python migrate.py   # schema را امن به‌روز می‌کند، داده را پاک نمی‌کند
sudo systemctl start mavara-bot mavara-api

# سایت:
# فقط فایل‌های استاتیک جدید را جایگزین /opt/mavara-home-website کنید — چیز دیگری لازم نیست
```

## نکات امنیتی قبل از رفتن به Production

- [x] ~~`API_ADMIN_TOKEN` پیش‌فرض~~ — دیگر استفاده نمی‌شود؛ به‌جایش:
- [ ] `JWT_SECRET` را حتماً با یک مقدار واقعی تصادفی پر کنید (نه خالی، نه پیش‌فرض)
- [ ] برای هر ادمین واقعی یک حساب جدا با `create_web_admin.py` بسازید — رمزهای مشترک/حدس‌زدنی استفاده نکنید
- [ ] HTTPS واقعی (نه self-signed) فعال باشد
- [ ] بک‌آپ دوره‌ای از `data/production.db` (طبق سیستم بک‌آپ موجود بات) روی مکان دیگری هم نگه‌داری شود
