# گزارش معماری — Mavara Home (نسخه ۹)

## ۱) مشکلات فعلی پروژه (قبل از این نسخه)

1. **منطق رزرو در فرانت**: ظرفیت/قیمت/وضعیت در جاوااسکریپت مرورگر محاسبه میشد — قابل جعل و غیرقابل اعتماد برای رزرو واقعی.
2. **بدون Backend و Database مشترک**: سایت و ربات تلگرام دو سیستم جدا میشدند؛ Single Source of Truth وجود نداشت.
3. **وضعیتهای رزرو پراکنده و ناهماهنگ** بود (چند لیست متفاوت در فایلهای مختلف).
4. **پنل ادمین ابتدایی**: بدون جستجو، فیلتر، خروجی Excel، مدیریت سانس/تقویم و مشاهده رسید.
5. **جریان پرداخت ناقص**: فقط فرم ساده؛ بدون آپلود رسید و گردش وضعیت.
6. **امنیت**: هیچ محدودیتی برای آپلود و هیچ ثبت وقایع (Audit Log) نبود.
7. **ساختار فایلها تخت** بود و توسعه ماژولار را سخت میکرد.

## ۲) فایلهایی که تغییر کردند / اضافه شدند

- **جدید**: `backend/` (server.js, src/service.js, src/store.js, package.json, .env.example, Dockerfile)
- **جدید**: `docker-compose.yml`، `database/migrations/001_init.sql`، `docs/API.md`، `docs/REPORT.md`، `README.md`، `tests/` (reservation.test.js, CASES.md)
- **تغییر**: `assets/js/app.js` (وضعیتها، dates/sessions/settings API، adapter MAAVARA_API_BASE)
- **تغییر**: `assets/js/site.js` (ویجت رزرو مرحلهبهمرحله + آپلود رسید)
- **تغییر**: `pages/admin/calendar.html` (جدید — تقویم و سانس)، `reservations.html` (بازنویسی)، `dashboard.html` (آمار امروز + تنظیمات پرداخت)، `events.html` (فیلدهای EN)

## ۳) معماری پیشنهادی و پیادهسازی

```
Website (Client)  ──┐
Admin Panel (Client)─┼──► REST API /api/v1 (backend) ──► Database
Telegram Bot (Client)┘           │                          ▲
                                 └── Service Layer ──────────┘
```
- **Single Source of Truth**: `backend/src/service.js` (رزرو، ظرفیت، رسید، وضعیت) — سایت/ادمین/ربات فقط Client.
- **Database Ready**: `database/migrations/001_init.sql` (users, events, sessions, reservations, audit_logs + UNIQUE برای سانس تکراری + محدودیت کد MAV-XXXXXX).
- **API Ready**: REST نسخهدار در `docs/API.md` و `backend/openapi.json` — ربات تلگرام از همین endpointها استفاده میکند.
- **Frontend باقی Client**: در نبود بکاند، fallback محلی (localStorage) برای دمو؛ با تنظیم `MAAVARA_API_BASE` فرانت مستقیماً به API وصل میشود.
- **جریان رزرو**: رویداد ← روز (تقویم شمسی) ← سانس (ظرفیت/قیمت/وضعیت) ← تعداد با ± ← خلاصه ← اطلاعات خریدار ← `pending_payment` ← آپلود رسید ← `receipt_uploaded` ← تأیید ادمین ← `approved` (یا rejected با توضیح)؛ سانسِ پر → لیست انتظار.
- **امنیت**: توکن ادمین فقط در `.env`؛ Validation سمت سرور؛ محدودیت رسید ~۱.۵MB؛ Audit Log برای همه تغییرات وضعیت؛ جلوگیری از سانس تکراری در DB و UI.

## ۴) محدودیت صادقانه

این بسته ZIP استاتیک است: بکاند بهصورت واقعی اجرا میشود ولی دیتابیس فعلاً JSON-file است؛ Postgres جایگزین فوری با همان schema میشود (migration آماده است). اتصال واقعی ربات تلگرام و درگاه بانکی نیازمند deploy است و بدون بازنویسی منطق انجام میشود.
