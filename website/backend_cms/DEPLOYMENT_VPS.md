# استقرار روی یک سرور ابری واقعی (VPS، دسترسی root/SSH کامل)

این راهنما برای وقتیه که یک VPS واقعی دارید (مثلاً پارس‌پک، با کمترین
تنظیمات: ۱ هسته / ۲ گیگ رم / ۲۵ گیگ فضا، Ubuntu 22.04) — نه هاست
اشتراکی. اگر هاست شما فقط پنل گرافیکی (سی‌پنل/دایرکت‌ادمین) و «Setup
Python App» داره، به‌جای این فایل سراغ `DEPLOYMENT.md` برید.

با یک VPS دیگه لازم نیست نگران این باشیم که پنل مسیر URL رو از
PATH_INFO حذف می‌کنه یا نه (همون دلیلی که در `DEPLOYMENT.md` باعث شد
مسیرها دوبار ثبت بشن) — اینجا خودمون مستقیم Nginx و systemd رو
کانفیگ می‌کنیم، دقیقاً مثل `bot/DEPLOYMENT.md` (که برای پروژه بات
نوشته شده). این دو کاملاً مستقل‌ان: می‌تونید فقط سایت رو اینجا بالا
بیارید، یا (اگر بعداً خواستید بات رو هم فعال کنید) هر دو رو روی همون
یک سرور، کنار هم.

## معماری روی سرور

```
اینترنت
   │
   ▼
Nginx (پورت ۴۴۳، HTTPS)
   │
   ├── فایل‌های استاتیک سایت (index.html, pages/, assets/) — مستقیم از دیسک
   ├── /media/*  — مستقیم از دیسک (هرگز از طریق پایتون پروکسی نمی‌شود)
   │
   └── /api/v1/*  و  /v1/*  →  proxy  →  gunicorn (پورت 8790، فقط داخلی)
                                              │
                                              ▼
                                    دیتابیس backend_cms (SQLite خودش)
```

## ۱. پیش‌نیاز روی سرور

```bash
sudo apt update && sudo apt install -y python3 python3-venv nginx certbot python3-certbot-nginx
sudo useradd -r -s /bin/false mavara
```

## ۲. کپی کردن پروژه

فقط پوشه‌ی `website/` این ریپو رو (نه `bot/`) روی سرور بیارید:

```bash
sudo mkdir -p /opt/mavara-website
# پوشه‌ی website/ را روی سرور آپلود کنید (scp/git clone) و محتوایش را در
# /opt/mavara-website بگذارید — یعنی /opt/mavara-website/backend_cms،
# /opt/mavara-website/index.html، /opt/mavara-website/media و... کنار هم
sudo chown -R mavara:mavara /opt/mavara-website
```

## ۳. نصب و پیکربندی بک‌اند

```bash
cd /opt/mavara-website/backend_cms
sudo -u mavara python3 -m venv venv
sudo -u mavara venv/bin/pip install -r requirements-vps.txt   # شامل gunicorn هم می‌شود

sudo -u mavara cp .env.example .env
sudo -u mavara nano .env
# پر کنید:
#   JWT_SECRET=<یک رشته‌ی طولانی و تصادفی — با دستور زیر بسازید>
#     python3 -c "import secrets; print(secrets.token_hex(32))"
#   (MEDIA_ROOT را خالی بگذارید — پیش‌فرض همان website/media کنار همین پوشه است)

sudo -u mavara venv/bin/python create_admin.py
# نام کاربری و رمز عبور (حداقل ۱۰ کاراکتر) را وارد کنید — همین‌ها را در
# pages/admin/login.html سایت استفاده خواهید کرد.
```

## ۴. راه‌اندازی به‌عنوان سرویس (systemd)

```bash
sudo cp deploy/mavara-cms.service /etc/systemd/system/
sudo nano /etc/systemd/system/mavara-cms.service   # اگر مسیر را غیر از /opt/mavara-website گذاشتید، اصلاح کنید

sudo systemctl daemon-reload
sudo systemctl enable --now mavara-cms

sudo systemctl status mavara-cms
sudo journalctl -u mavara-cms -f   # لاگ زنده
```

## ۵. تنظیم Nginx (سرو سایت + پروکسی API)

```bash
sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/mavara-website
sudo nano /etc/nginx/sites-available/mavara-website
# دامنه (server_name) و مسیرها را با دامنه/مسیر واقعی خودتان جایگزین کنید

sudo ln -s /etc/nginx/sites-available/mavara-website /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# گواهی HTTPS واقعی (اجباری — رمز ادمین هرگز نباید بدون رمزنگاری منتقل شود):
sudo certbot --nginx -d your-domain.example.com
```

## ۶. تست نهایی

```bash
curl https://your-domain.example.com/api/v1/events
# باید {"data":[]} یا لیست رویدادها را برگرداند

curl https://your-domain.example.com/
# باید index.html سایت را برگرداند
```

بعد در مرورگر: `https://your-domain.example.com/pages/admin/login.html`
با حساب مرحله‌ی ۳ وارد شوید و یک رویداد/عکس تست بسازید — مطمئن شوید
لینک عکس (`https://your-domain.example.com/media/...`) هم باز می‌شود.

## به‌روزرسانی نسخه‌ی جدید

```bash
cd /opt/mavara-website
sudo systemctl stop mavara-cms
# فایل‌های کد را جایگزین کنید (backend_cms/data/ و backend_cms/.env و
# website/media/ را دست نزنید — دیتای واقعی همان‌جاست)
sudo systemctl start mavara-cms
```

## نکات امنیتی قبل از رفتن به Production

- [ ] `JWT_SECRET` را حتماً با یک مقدار واقعی تصادفی پر کنید
- [ ] برای هر ادمین واقعی یک حساب جدا با `create_admin.py` بسازید
- [ ] HTTPS واقعی (نه self-signed) فعال باشد
- [ ] `sudo ufw allow 'Nginx Full' && sudo ufw allow OpenSSH && sudo ufw enable` — فایروال پایه
- [ ] بک‌آپ دوره‌ای از `backend_cms/data/content.db` و `media/` روی جای دیگری هم نگه‌داری شود

## اگر بعداً خواستید `bot/` را هم روی همین سرور فعال کنید

این دو پروژه کاملاً مستقل‌اند (دیتابیس جدا، پورت جدا) — می‌توانید
`bot/DEPLOYMENT.md` را هم دنبال کنید و کنار همین یکی، روی همان سرور،
با یک Nginx (چند تا `server{}` یا چند `location`) هر دو را سرو کنید.
همون‌جا که این سرور در فرانکفورت/خارج از ایران باشد، مزیت اضافه‌اش
اینه که به `api.telegram.org` (فیلتر داخل ایران) مستقیم دسترسی داره.
