# ۰۸ — توسعه

## راه‌اندازی محلی

```bash
git clone <repo> && cd MavaraHome/bot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

در `.env` حداقل این‌ها را پر کن:
```
ENV=development
JWT_SECRET=<هر رشته‌ی تصادفی>
# BOT_TOKEN فقط اگر می‌خواهی خود ربات را هم تست کنی
```

```bash
python3 migrate.py            # ساخت دیتابیس
python3 seed_database.py      # داده‌ی تستی (فقط غیرپروداکشن)
python3 create_web_admin.py   # حساب پنل
```

**بالا آوردن سایت + API با هم روی یک پورت:**
```bash
STATIC_ROOT=../website python3 -m api.server
#   سایت:  http://127.0.0.1:8788
#   پنل:   http://127.0.0.1:8788/pages/admin/login.html
```

این ساده‌ترین راه است چون هم‌مبدأ می‌شود و نیازی به تنظیم CORS یا
`MAAVARA_API_BASE` نیست. برای ربات، ترمینال دوم: `python3 bot.py`.

## تست

```bash
cd bot && ENV=test python3 test_bot.py
```

۸۱ تست، بدون pytest — یک اجراکننده‌ی دست‌ساز با دکوریتور `@test("نام")`.
دو محافظ ایمنی: اگر `ENV=production` باشد بلافاصله خارج می‌شود، و در هر
حالت روی یک فایل موقت کار می‌کند که آخرش پاک می‌شود.

**چه چیزی پوشش دارد:** ماشین وضعیت رزرو، ریاضیات ظرفیت، لیست انتظار،
همزمانی، تبدیل تاریخ جلالی، اعتبارسنجی‌ها، ماتریس دسترسی، امضای QR، ادغام
هویت مشتری، بانک پرسش‌های متداول، و مایگریشن‌های اخیر.

**چه چیزی پوشش ندارد — صادقانه:**
- هیچ‌کدام از ۶۷ مسیر HTTP (تست در سطح تابع است، نه شبکه)
- هیچ‌کدام از ۱۷۵ هندلر تلگرام
- کل جاوااسکریپت و HTML
- خروجی واقعی PDF و ارسال واقعی SMTP

برای این‌ها روش پذیرفته‌شده‌ی پروژه، **راه‌اندازی یک سرور روی دیتابیس
یک‌بارمصرف و زدن `curl`** است — الگویش در بخش «بازتولید ایزوله» در
[`09-troubleshooting.md`](09-troubleshooting.md).

### نوشتن تست برای یک باگ

قانون: **اول ثابت کن تستت روی کد قبلی fail می‌شود.** واقعاً امتحانش کن —
موقتاً اصلاح را برگردان، تست را اجرا کن، ببین قرمز می‌شود، بعد اصلاح را
برگردان. تستی که هرگز fail نشده، چیزی را تضمین نمی‌کند.

## قراردادهای کد

- **کامنت «چرا» را توضیح می‌دهد، نه «چه».** ~۱۸٪ خطوط بک‌اند کامنت است و
  این عمدی است. وقتی گزینه‌ای را رد می‌کنی، دلیل ردش را بنویس.
- **تکرار ثابت‌ها ممنوع.** یک تعریف مرجع بساز و import کن.
- **نام‌ها انگلیسی، متن کاربر فارسی.**
- **`except` خالی نه**، مگر دلیلش کنارش نوشته شده باشد.
- **لایه‌بندی را نشکن:** منطق در `services/`، SQL در `repositories/`،
  انتقال در `api/` و `handlers/`.

---

# دستورالعمل‌ها

## چطور یک تنظیم جدید اضافه کنم

مثلاً یک متن جدید که ادمین بتواند عوض کند.

1. `bot/database/schema.py` → `DEFAULT_SETTINGS`: کلید و مقدار پیش‌فرض.
2. `bot/services/settings_service.py`:
   - `EDITABLE_SETTINGS`: کلید → برچسب فارسی
   - `SETTINGS_FIELD_TYPES`: `text` / `textarea` / `int`
   - اگر عددی است: `SETTINGS_INT_RANGE`
   - اگر متن عمومی سایت است: به `CONTENT_KEYS` هم اضافه کن تا از
     `/api/v1/site-content` سرو شود
3. `website/pages/admin/settings.html` → آرایه‌ی `TABS`: کلید را در تب
   مناسب بگذار. **اگر این مرحله را فراموش کنی، تنظیم در پنل نامرئی می‌شود**
   (`docs/generate.py --check` همین را می‌گیرد).
4. اگر متن سایت است: در `site.js` به `SITE_CONTENT_MAP` اضافه کن و در HTML
   عنصر مربوطه را `data-i18n="..."` بده.

بدون مایگریشن — `DEFAULT_SETTINGS` در هر استارت با `INSERT OR IGNORE` درج
می‌شود.

## چطور یک اندپوینت جدید بسازم

1. اگر منطق دارد → تابعش در `services/`؛ اگر فقط داده می‌خواهد → در
   `database/repositories/`.
2. `bot/api/server.py` → داخل متد `do_*` مناسب:
   ```python
   if path == "/api/v1/admin/my-thing":
       if not self._is_admin():
           return self._send_json(401, {"error": "unauthorized"})
       body = self._read_json_body()
       result = my_service.do_it(**body)
       return self._send_json(200, {"data": result})
   ```
   مسیر با پارامتر → `re.match(r"^/api/v1/admin/my-thing/(\d+)$", path)`.
   **اگر مسیر فارسی/غیر-ASCII می‌گیرد، حتماً `unquote()` کن.**
3. `website/assets/js/app.js` → یک متد در `API.*`.
4. صفحه‌ی پنل → صدا زدنش **داخل `try/catch`**.
5. `python3 docs/generate.py` تا مرجع API به‌روز شود.

> ❗ مرحله‌ی ۲ همان مرحله‌ای است که یک بار فراموش شد و دکمه‌ی حذف رویداد
> هفته‌ها بی‌صدا کار نکرد.

## چطور یک ستون/جدول جدید اضافه کنم

1. `bot/database/schema.py`:
   - `SCHEMA_VERSION` را یکی بالا ببر
   - ستون را به `CREATE TABLE` اضافه کن (برای نصب تازه)
   - **و** به فهرست `ALTER TABLE ADD COLUMN` (برای دیتابیس موجود)
   - اگر داده باید منتقل شود: یک backfill محافظت‌شده با `stored_version`
2. `database/repositories/<table>.py`: فیلد را به `_FIELDS` اضافه کن.
   اگر JSON است، مثل `gallery` جدا هندلش کن.
3. اگر در API دیده می‌شود: به تابع قالب‌بندی (`_event_public` و مشابهش) اضافه کن.
4. `docs/03-data-model.md` را به‌روز کن (`generate.py --check` نبودنش را می‌گیرد).
5. تست بنویس.
6. روی سرور: `migrate.py` یا فقط ریستارت ربات.

**قواعد:** فقط افزایشی؛ ستون حذف نکن؛ `NOT NULL` بدون `DEFAULT` روی جدول
پرداده نگذار.

## چطور یک وضعیت جدید رزرو اضافه کنم

⚠️ **پرخطرترین تغییر این سیستم.** ترتیب را رعایت کن:

1. **اگر صندلی نگه می‌دارد**، به `SEAT_HOLDING_STATUSES` در
   `database/repositories/sessions.py` اضافه‌اش کن. (فراموشی = آزاد شدن
   بی‌صدای صندلی‌ها.)
2. گذارها را با `set_status_if_any()` بنویس، نه `set_status()` خام.
3. برچسبش را به `bot/texts/fa.py` و به نگاشت وضعیت‌ها در
   `website/pages/admin/reservations.html` اضافه کن.
4. آیکون و شمارش‌های `services/channel_service.py` را به‌روز کن.
5. تصمیم بگیر که آیا زمان‌بند انقضا باید هدفش بگیرد یا نه
   (`list_expired_pending` فقط `pending_payment` را می‌بیند).
6. تستی بنویس که ثابت کند صندلی همان‌طور که انتظار داری رفتار می‌کند.
7. [`docs/03-data-model.md`](03-data-model.md) را به‌روز کن.

## چطور یک صفحه‌ی جدید به پنل اضافه کنم

الگو در [`05-frontend-and-design.md`](05-frontend-and-design.md) بخش پایانی.
خلاصه: سایدبار را از `dashboard.html` کپی کن، لینک جدید را به سایدبار
**همه‌ی** صفحات اضافه کن، اولین خط اسکریپت را `API.auth.check()` بگذار، فرم
را داخل `.feedback-box` بگذار، و هر `fetch` را `try/catch` کن.

---

## مستندات

بعد از هر تغییر ساختاری:

```bash
python3 docs/generate.py          # بازتولید مرجع API و کلیدهای تنظیمات
python3 docs/generate.py --check  # همان چیزی که CI اجرا می‌کند
```

`--check` سه چیز را بررسی می‌کند: به‌روز بودن فایل‌های تولیدی، اینکه هر جدول
در `03-data-model.md` نام برده شده، و اینکه هر کلید تنظیمات در صفحه‌ی تنظیمات
پنل قابل دسترس است.

## تعریف «کارِ تمام‌شده»

در [`../AGENTS.md`](../AGENTS.md) است. خلاصه: کد + تست سبز + ورودی CHANGELOG
با دلیل و شواهد + به‌روزرسانی سند مربوطه + ذکر نیاز به ریستارت در پیام دیپلوی.

---

بعدی: [`10-state-and-roadmap.md`](10-state-and-roadmap.md)
