# ۰۹ — عیب‌یابی

این سند از **باگ‌های واقعی که در این پروژه رخ داده‌اند** ساخته شده، نه از
حدس. اگر به مشکلی خوردی، اول جدول علائم را نگاه کن.

## جدول سریع: علامت ← علت

| علامت | محتمل‌ترین علت | کجا را نگاه کن |
|---|---|---|
| دکمه‌ای در پنل «هیچ کاری نمی‌کند» | مسیر API وجود ندارد → ۴۰۴ خاموش | تب Network مرورگر؛ بعد `do_GET`/`do_POST`/`do_PATCH`/`do_DELETE` در `api/server.py` |
| عملیات انجام می‌شود ولی پیامی نمی‌آید | `fetch` بدون `try/catch` | تابع مربوطه در فایل HTML پنل |
| صندلی بی‌دلیل آزاد شده | وضعیت جدید در `SEAT_HOLDING_STATUSES` نیست | `database/repositories/sessions.py` |
| سانس بیش از ظرفیت رزرو دارد | جایی ظرفیت بدون تراکنش اتمیک بررسی شده | `create_reservation_locked` و خواهرانش |
| تصویر آپلودشده نمایش داده نمی‌شود | فراموشی `pp()` روی مسیر رسانه | فراخوانی رندر در فایل صفحه |
| صفحه‌ی عضوی با نام فارسی ۴۰۴ می‌دهد | مسیر URL قبل از تطبیق `unquote()` نشده | الگوی regex مسیر در `api/server.py` |
| پیام «ذخیره شد» زیر بخش اشتباه ظاهر می‌شود | شناسه‌ی DOM از متن فارسی ساخته شده و خالی شده | تابع تولید شناسه در فایل صفحه |
| تغییرات بعد از دیپلوی دیده نمی‌شود | کش مرورگر | `Ctrl+Shift+R`؛ هدرهای no-cache در nginx |
| تابعی ناگهان `NameError` می‌دهد | `import` محلی داخل یک شاخه، نام را برای کل تابع محلی کرده | خود تابع؛ دنبال `from … import …` داخل بدنه بگرد |
| ایمیل نمی‌رود ولی خطایی هم نیست | `SMTP_HOST` خالی است → ایمیل در لاگ چاپ می‌شود | `.env` و `logs/app.log` |
| ربات به دستورها جواب نمی‌دهد | سرویس `mavara-bot` پایین است یا `BOT_TOKEN` غلط | `systemctl status mavara-bot` |
| پنل کار می‌کند ولی ربات تغییرات را نمی‌بیند | فقط یکی از دو سرویس ریستارت شده | هر دو را ریستارت کن |
| `database is locked` | نوشتن هم‌زمان دو پروسه | بخش پایانی همین سند |
| تنظیمی در پنل نیست ولی در ربات هست | کلید در `EDITABLE_SETTINGS` هست ولی در گروه‌بندی صفحه‌ی تنظیمات نیامده | آرایه‌ی `TABS` در `pages/admin/settings.html` |

## الگوهای خرابی تکرارشونده‌ی این کدبیس

این‌ها بیش از یک بار اتفاق افتاده‌اند. قبل از دیباگ عمیق، این‌ها را رد کن.

### ۱. مسیر API که وجود ندارد → «دکمه مرده»

مسیریابی دستی است. یک تابع در repository نوشته می‌شود، فرانت‌اند صدایش
می‌زند، ولی هیچ‌کس مسیر را به متد `do_*` اضافه نکرده. نتیجه: ۴۰۴ عمومی. و
چون فرانت `catch` ندارد، خطا بلعیده می‌شود و کاربر فقط می‌بیند «هیچ اتفاقی
نیفتاد».

**تشخیص:** تب Network. اگر ۴۰۴ دیدی، مسیر را در `api/server.py` بگرد:
```bash
grep -n "admin/events" bot/api/server.py
```

**پیشگیری:** هر endpoint جدید نیاز به سه چیز دارد: تابع repository، مسیر در
`server.py`، و wrapper در `app.js`.

### ۲. وضعیت جدیدی که صندلی را آزاد می‌کند

چون ستون `status` متن آزاد است، وضعیت ناشناخته خطا نمی‌دهد؛ فقط از فیلتر
می‌افتد بیرون و صندلی آزاد می‌شود. شرح کامل در
[`03-data-model.md`](03-data-model.md).

**تشخیص:** ظرفیت آزاد سانس را قبل و بعد از عملیات مقایسه کن:
```bash
cd bot && ENV=production python3 -c "
from database.repositories import sessions as s
print(s.reserved_count(SESSION_ID))"
```

### ۳. مسیر رسانه بدون `pp()`

API مسیرهای نسبی برمی‌گرداند (`media/portfolio/123.jpg`). بسته به اینکه
صفحه در ریشه است یا در `pages/`، این مسیر باید متفاوت پیشوند بگیرد. تابع
`pp()` در `site.js` این کار را می‌کند. فراموشی‌اش یعنی تصویر ۴۰۴.

**تشخیص:** در Network، درخواست تصویر مسیر اشتباه دارد (مثلاً
`/pages/media/...` به‌جای `/media/...`).

### ۴. متن فارسی در شناسه‌ی DOM

اگر شناسه‌ای را از روی عنوان فارسی بسازی و کاراکترهای غیر-ASCII را حذف کنی،
رشته‌ی **خالی** می‌ماند — و همه‌ی بخش‌ها یک شناسه‌ی یکسان می‌گیرند.
`getElementById` اولی را برمی‌گرداند و پیام‌ها زیر بخش اشتباه می‌نشینند.

**قاعده:** شناسه را از **اندیس عددی** یا کلید انگلیسی بساز، نه از متن فارسی.

### ۵. اسلاگ فارسی در URL

نام‌های فارسی اسلاگ فارسی می‌سازند که در URL درصدکدگذاری می‌شوند. اگر مسیر
خام را با regex تطبیق بدهی، هیچ‌وقت match نمی‌شود.

**قاعده:** قبل از تطبیق `unquote()` کن و در الگو `%` را هم مجاز بگذار.

### ۶. سایه افتادن نام ماژول در پایتون

یک `from database.repositories import settings as settings_repo` داخل بدنه‌ی
یک تابع، آن نام را برای **کل تابع** محلی می‌کند — حتی در شاخه‌هایی که قبل
از آن خط اجرا می‌شوند. نتیجه: `NameError` در جایی که هیچ ربطی به آن import
ندارد.

**قاعده:** import را بالای ماژول بگذار، مگر برای شکستن حلقه‌ی وابستگی.

### ۷. کش مرورگر بعد از دیپلوی

فایل‌های استاتیک بدون هش نسخه سرو می‌شوند. `nginx.conf.example` هدرهای
no-cache دارد، ولی اگر تنظیمات سرور با آن هماهنگ نباشد، ادمین نسخه‌ی قدیمی
پنل را می‌بیند و فکر می‌کند تغییرات اعمال نشده.

**قاعده:** بعد از هر دیپلوی فرانت‌اند، `Ctrl+Shift+R`.

## جعبه‌ابزار دیباگ

### سلامت کلی سیستم
```bash
cd /opt/MavaraHome/bot
sudo -u mavara ./venv/bin/python health_check.py    # باید ۱۱/۱۱ بدهد
```
یازده بررسی: متغیرهای محیطی، وجود فایل دیتابیس، نسخه‌ی اسکیما، وجود
جدول‌ها، کلیدهای خارجی، ردیف‌های یتیم، ادمین‌ها، کارت بانکی، لاگ‌ها، پوشه‌ی
بکاپ، و صحت importها.

### لاگ‌ها
```bash
journalctl -u mavara-api -n 100 --no-pager
journalctl -u mavara-bot -n 100 --no-pager
tail -f /opt/MavaraHome/bot/logs/app.log
```

### وضعیت سرویس‌ها
```bash
systemctl status mavara-api mavara-bot
```

### پرس‌وجوی مستقیم دیتابیس
```bash
cd /opt/MavaraHome/bot
sudo -u mavara ./venv/bin/python -c "
from database.connection import get_connection
with get_connection() as c:
    for r in c.execute('''
        SELECT r.id, r.status, r.people, s.session_date, s.session_time, e.title
        FROM reservations r
        JOIN sessions s ON s.id = r.session_id
        JOIN events e ON e.id = s.event_id
        ORDER BY r.id DESC LIMIT 10''').fetchall():
        print(dict(r))
"
```

### تست یک اندپوینت
```bash
curl -s http://127.0.0.1:8788/api/v1/events | python3 -m json.tool | head -30

TOKEN=$(curl -s -X POST http://127.0.0.1:8788/api/v1/admin/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"USER","password":"PASS"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")
curl -s http://127.0.0.1:8788/api/v1/admin/reservations -H "Authorization: Bearer $TOKEN"
```

### اجرای تست‌ها
```bash
cd bot && ENV=test python3 test_bot.py
```
هرگز به دیتابیس واقعی دست نمی‌زند: اگر `ENV=production` باشد بلافاصله خارج
می‌شود و در هر حالت یک فایل موقت می‌سازد.

### بازتولید یک باگ به‌صورت ایزوله
```bash
cd bot
rm -f /tmp/dbg.db
ENV=test DB_PATH=/tmp/dbg.db python3 -c "
from database.schema import init_db; init_db()
from utils.auth import hash_password
from database.repositories import web_admins as wa
h,s = hash_password('testpass123'); wa.create('dbg', h, s, role='owner')
print('ready')"
ENV=test DB_PATH=/tmp/dbg.db API_PORT=8799 STATIC_ROOT=../website \
  JWT_SECRET=dbg python3 api/server.py
```
حالا کل سایت و پنل روی `http://127.0.0.1:8799` بالاست، روی یک دیتابیس
یک‌بارمصرف.

## مشکلات عملیاتی

### `database is locked`
دو پروسه هم‌زمان می‌نویسند. اول ببین آیا یک اسکریپت دستی (مثل `migrate.py`
یا یک شل پایتون باز) دیتابیس را نگه داشته. اگر مزمن شد، حالت WAL را فعال
کن — قبل از فکر کردن به مهاجرت از SQLite.

### ایمیل نمی‌رود
`SMTP_HOST` خالی یعنی «ایمیل را به‌جای ارسال، در لاگ چاپ کن» — این حالت
پیش‌فرض توسعه است. اگر روی سرور واقعی ایمیل نمی‌رود، اول `.env` را ببین،
بعد لاگ را بگرد:
```bash
grep -i "SMTP not configured" /opt/MavaraHome/bot/logs/app.log
```

### سانسی بیش از ظرفیت رزرو دارد
معمولاً نتیجه‌ی یک باگ ظرفیت است که بعداً رفع شده و ردیف‌های قدیمی مانده‌اند.
سیستم کرش نمی‌کند (ظرفیت آزاد را صفر نشان می‌دهد و جلوی رزرو جدید را
می‌گیرد). برای پیدا کردنشان:
```bash
cd /opt/MavaraHome/bot && sudo -u mavara ./venv/bin/python -c "
from database.connection import get_connection
from database.repositories.sessions import SEAT_HOLDING_STATUS_SQL
with get_connection() as c:
    rows = c.execute(f'''SELECT s.id, s.session_date, s.session_time, s.capacity,
        (SELECT COALESCE(SUM(people),0) FROM reservations r
         WHERE r.session_id=s.id AND r.status IN ({SEAT_HOLDING_STATUS_SQL})) held
        FROM sessions s''').fetchall()
    for r in rows:
        if r['held'] > r['capacity']: print(dict(r))
"
```

### بازگرداندن دیتابیس از بکاپ
بکاپ‌ها خودکار در `bot/backups/` ساخته می‌شوند. برای بازگردانی: هر دو سرویس
را متوقف کن، فایل بکاپ را روی `data/production.db` کپی کن، `health_check.py`
را اجرا کن، بعد سرویس‌ها را بالا بیاور.

## وقتی هیچ‌کدام جواب نداد

۶۴ ورودی `CHANGELOG.md` تاریخچه‌ی کامل هر باگی است که تا امروز رخ داده —
با علامت، ریشه، و راه‌حل. جست‌وجو در آن معمولاً سریع‌تر از دیباگ از صفر است:

```bash
grep -n -i "کلیدواژه" CHANGELOG.md
```

و در نهایت: این کدبیس عمداً پرکامنت است (~۱۸٪ خطوط بک‌اند). اگر کدی عجیب به
نظر می‌رسد، احتمالاً دلیلش دقیقاً بالای همان خط نوشته شده.
