# ۰۷ — عملیات و دیپلوی

## شکل استقرار

یک VPS اوبونتو، سه چیز:

| | |
|---|---|
| `nginx` | فایل‌های استاتیک `website/` را سرو می‌کند + `/api/v1/` و `/media/` را به پورت ۸۷۸۸ پروکسی می‌کند |
| `mavara-api.service` | پروسه‌ی API (`python -m api.server`) |
| `mavara-bot.service` | پروسه‌ی ربات (`python bot.py`) |

**مایگریشن**: هر دو سرویس در استارت `init_db()` را صدا می‌زنند، پس هرکدام
زودتر بالا بیاید اسکیما را جلو می‌برد و دیگری کاری نمی‌کند (همه‌ی دستورها
idempotent هستند). تا v18 فقط ربات این کار را می‌کرد — یعنی اگر ربات بالا
نمی‌آمد، سایت و پنل روی دیتابیس مایگریت‌نشده بالا می‌آمدند و ۵۰۰ می‌دادند.

هر دو سرویس زیر کاربر `mavara` اجرا می‌شوند و یک فایل SQLite مشترک دارند.

## دیپلوی روزمره

```bash
cd /opt/MavaraHome
git pull origin <branch>
sudo systemctl restart mavara-api mavara-bot
```

**چه وقت چه کاری لازم است:**

| چه چیزی عوض شده | ریستارت؟ | مایگریشن؟ |
|---|---|---|
| فقط `website/` (HTML/CSS/JS) | ❌ نه | ❌ نه — فقط `Ctrl+Shift+R` در مرورگر |
| `bot/services/`، `bot/api/`، `bot/handlers/` | ✅ **هر دو سرویس** | ❌ |
| `bot/database/schema.py` با `SCHEMA_VERSION` بالاتر | ✅ هر دو | ✅ خودکار در استارت ربات، یا دستی با `migrate.py` |
| `.env` | ✅ هر دو | ❌ |

> **همیشه هر دو سرویس را ریستارت کن**، نه فقط API. هر دو `services/` را
> import می‌کنند؛ ریستارت یکی یعنی دو نسخه‌ی متفاوت از منطق تجاری هم‌زمان
> اجرا می‌شوند.

### بعد از دیپلوی چه چیزی را چک کنیم

```bash
systemctl status mavara-api mavara-bot          # هر دو active باشند
journalctl -u mavara-api -n 30 --no-pager       # بدون traceback
curl -s https://mavarahome.com/api/v1/events | head -c 200
```
و در مرورگر: یک صفحه‌ی عمومی + ورود به پنل.

## نصب اولیه روی سرور تازه

راهنمای گام‌به‌گام فعلی در [`../bot/DEPLOYMENT.md`](../bot/DEPLOYMENT.md)
است. خلاصه‌اش:

1. `apt install python3 python3-venv nginx certbot python3-certbot-nginx`
2. ساخت کاربر سیستمی `mavara`؛ کلون پروژه در `/opt/MavaraHome`؛ مالکیت به `mavara`.
3. `python3 -m venv venv && pip install -r requirements.txt`
4. `cp .env.example .env` و پر کردن:
   - `BOT_TOKEN` — از BotFather
   - `JWT_SECRET` — با `python3 -c "import secrets; print(secrets.token_hex(32))"`
   - `BOOTSTRAP_ADMIN_IDS` — آیدی عددی تلگرام اولین ادمین‌ها
   - `ENV=production`
   - تنظیمات SMTP (اگر خالی باشد، ایمیل‌ها فقط در لاگ چاپ می‌شوند)
5. `python3 migrate.py` سپس `python3 health_check.py` (باید ۱۱/۱۱ بدهد)
6. `python3 create_web_admin.py` — حساب پنل وب (حداقل ۱۰ کاراکتر رمز)
7. کپی دو یونیت از `bot/deploy/`، `daemon-reload`، `enable --now`
8. کانفیگ nginx از `bot/deploy/nginx.conf.example`، سپس `certbot --nginx`

> ⚠️ یونیت‌های آماده `WorkingDirectory=/opt/MavaraHome/bot` دارند. اگر
> مسیر نصبت فرق دارد، قبل از فعال‌سازی ویرایششان کن.

> ⚠️ `seed_database.py` را **هرگز** روی پروداکشن اجرا نکن — داده‌ی تستی
> می‌سازد. `seed_portfolio.py` بی‌خطر و افزایشی است.

## متغیرهای محیطی

| متغیر | پیش‌فرض | نکته |
|---|---|---|
| `BOT_TOKEN` | ندارد | بدون آن ربات بالا نمی‌آید (API می‌آید) |
| `JWT_SECRET` | خالی | **اگر خالی بماند ورود بی‌صدا خراب می‌شود.** عوض کردنش همه‌ی توکن‌ها را باطل می‌کند |
| `ENV` | `production` | تنها چیزی که فایل دیتابیس را انتخاب می‌کند |
| `DB_PATH` | `data/<env>.db` | مسیر صریح دیتابیس |
| `BOOTSTRAP_ADMIN_IDS` | خالی | فقط در اولین اجرا خوانده می‌شود |
| `API_PORT` | `8788` | |
| `STATIC_ROOT` | خالی | اگر ست شود، API خودش سایت را هم سرو می‌کند (حالت تک‌پروسه، مناسب توسعه) |
| `SMTP_HOST` و بقیه‌ی `SMTP_*` | خالی | **خالی یعنی ایمیل به‌جای ارسال در لاگ چاپ شود** |
| `DEBUG` | `false` | در پروداکشن حتی اگر `true` باشد اجباراً خاموش می‌شود |
| `API_ADMIN_TOKEN` | `1234` | **منسوخ** — هیچ اندپوینتی دیگر نمی‌پذیردش |

هر چیز دیگری که ادمین باید بتواند عوض کند، در جدول `settings` است نه اینجا.

## بکاپ و بازیابی

بکاپ خودکار: حلقه‌ی پس‌زمینه‌ی ربات دوره‌ای از دیتابیس در `bot/backups/`
کپی می‌گیرد.

**بکاپ دستی:**
```bash
cp /opt/MavaraHome/bot/data/production.db ~/mavara-$(date +%F-%H%M).db
```

**بازیابی:**
```bash
sudo systemctl stop mavara-api mavara-bot
sudo -u mavara cp <فایل-بکاپ> /opt/MavaraHome/bot/data/production.db
cd /opt/MavaraHome/bot && sudo -u mavara ./venv/bin/python health_check.py
sudo systemctl start mavara-api mavara-bot
```

> بکاپ روی همان سرور، بکاپ نیست. یک کپی خارج از سرور نگه دار — این فایل
> شامل تمام رزروها و اطلاعات تماس مشتریان است.

**چیزی که در بکاپ دیتابیس نیست:** فایل‌های آپلودشده. `bot/media/` (پوستر و
گالری) و `bot/private_media/` (رسیدهای پرداخت) باید جدا کپی شوند.

## پایش

```bash
systemctl status mavara-api mavara-bot
journalctl -u mavara-api -f
journalctl -u mavara-bot -n 100 --no-pager
tail -f /opt/MavaraHome/bot/logs/app.log
cd /opt/MavaraHome/bot && sudo -u mavara ./venv/bin/python health_check.py
```

`health_check.py` یازده چیز را بررسی می‌کند: متغیرهای محیطی، وجود فایل
دیتابیس، نسخه‌ی اسکیما، وجود جدول‌ها، کلیدهای خارجی، ردیف‌های یتیم، ادمین‌ها،
کارت بانکی فعال، لاگ‌ها، پوشه‌ی بکاپ، و صحت importها.

## رانبوک حادثه

### سایت بالا نمی‌آید
```bash
systemctl status nginx mavara-api
nginx -t                      # خطای کانفیگ؟
journalctl -u mavara-api -n 50 --no-pager
curl -s http://127.0.0.1:8788/api/v1/events | head -c 200   # آیا خود API سالم است؟
```
اگر API جواب می‌دهد ولی سایت نه → مشکل از nginx است. اگر API هم جواب
نمی‌دهد → لاگ سرویس را بخوان.

### ربات جواب نمی‌دهد
```bash
systemctl status mavara-bot
journalctl -u mavara-bot -n 50 --no-pager
```
معمول‌ترین علت‌ها: `BOT_TOKEN` غلط یا باطل‌شده؛ کرش در استارت به‌خاطر خطای
مایگریشن؛ یا نبود دسترسی شبکه به تلگرام.

### پنل کار می‌کند ولی ربات تغییرات را نمی‌بیند (یا برعکس)
فقط یکی از دو سرویس ریستارت شده. هر دو را ریستارت کن.

### ایمیل نمی‌رود
`SMTP_HOST` را در `.env` چک کن. اگر خالی است، ایمیل‌ها عمداً فقط چاپ می‌شوند:
```bash
grep -i "SMTP not configured" /opt/MavaraHome/bot/logs/app.log
```

### `database is locked`
یک اسکریپت دستی یا شل پایتونِ باز دیتابیس را نگه داشته. ببندش. اگر تکرار
شد، فعال کردن حالت WAL اولین قدم است — نه مهاجرت از SQLite.

### ورود ادمین کار نمی‌کند
اگر `JWT_SECRET` عوض شده باشد، همه‌ی توکن‌های صادرشده باطل‌اند — کافی است
دوباره وارد شوی. اگر خالی باشد، ورود بی‌صدا خراب می‌شود.

### مایگریشن خطا داد
```bash
cd /opt/MavaraHome/bot
sudo -u mavara ./venv/bin/python migrate.py     # روی پروداکشن تأیید می‌خواهد
sudo -u mavara ./venv/bin/python health_check.py
```
مایگریشن‌ها فقط افزایشی‌اند و هر `ALTER` جداگانه try/except شده، پس خطای
«ستون تکراری» بی‌خطر است. اگر چیز دیگری بود، اول از دیتابیس بکاپ بگیر.

### بازگشت به نسخه‌ی قبل (rollback)
```bash
cd /opt/MavaraHome && git log --oneline -5
git checkout <commit-قبلی>
sudo systemctl restart mavara-api mavara-bot
```
> ⚠️ اگر آن دیپلوی مایگریشن داشته، **اسکیما به عقب برنمی‌گردد** (down-migration
> نداریم). چون همه‌ی تغییرات افزایشی‌اند، کد قدیمی معمولاً با اسکیمای جدید
> کار می‌کند — ولی اگر نکرد، باید از بکاپ دیتابیس بازیابی کنی.

## چک‌لیست امنیتی

- [ ] `JWT_SECRET` واقعی و تصادفی است (نه خالی، نه مقدار نمونه)
- [ ] هر ادمین حساب کاربری خودش را دارد
- [ ] HTTPS با گواهی معتبر فعال است
- [ ] بکاپ دیتابیس **خارج از سرور** نگهداری می‌شود
- [ ] `bot/private_media/` (رسیدهای پرداخت مشتریان) از بیرون قابل دسترس نیست
- [ ] `.env` در گیت نیست

> ✅ **بررسی شد:** `.gitignore` درست کار می‌کند — `.env`، فایل‌های دیتابیس،
> `private_media/` و `__pycache__` هیچ‌وقت کامیت نشده‌اند (تنها چیزی که در
> تاریخچه هست `.env.example` است که عمدی و بی‌خطر است). این فایل‌ها روی
> دیسک سرور هستند ولی در مخزن نه.

---

بعدی: [`08-development.md`](08-development.md)
