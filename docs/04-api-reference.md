<!-- این فایل به‌صورت خودکار از روی کد تولید شده است. دستی ویرایشش نکن.
     بازتولید:  python3 docs/generate.py  -->
# ۰۴ — مرجع API
همه‌ی مسیرها زیر `/api/v1` هستند. مجموع **67** مسیر: 26 GET · 28 POST · 7 PATCH · 6 DELETE.
پاسخ موفق همیشه `{"data": …}` است و خطا `{"error": "…"}` با کد وضعیت متناسب (`400` اعتبارسنجی، `401` احراز هویت، `404` نبودن، `409` تعارض).

احراز هویت با هدر `Authorization: Bearer <token>` انجام می‌شود. توکن ادمین از `POST /api/v1/admin/login` و توکن مشتری از `POST /api/v1/auth/customer/verify-otp` گرفته می‌شود. جزئیات هر هندلر در `bot/api/server.py` است — مسیریابی دستی است، پس مسیر جدید باید صریحاً به متد `do_*` مربوطه اضافه شود وگرنه بی‌صدا ۴۰۴ می‌دهد.

## GET

| مسیر | دسترسی |
|---|---|
| `/api/v1/events` | عمومی |
| `/api/v1/events/{id}` | عمومی |
| `/api/v1/events/{id}/dates` | عمومی |
| `/api/v1/sessions` | عمومی |
| `/api/v1/admin/reservations` | ادمین (JWT) |
| `/api/v1/admin/waitlist` | ادمین (JWT) |
| `/api/v1/admin/broadcast-audience` | ادمین (JWT) |
| `/api/v1/admin/broadcasts` | ادمین (JWT) |
| `/api/v1/admin/settings` | ادمین (JWT) |
| `/api/v1/admin/bank-cards` | ادمین (JWT) |
| `/api/v1/admin/reservations/{id}/receipt` | ادمین (JWT) |
| `/api/v1/admin/activity` | ادمین (JWT) |
| `/api/v1/admin/dashboard-stats` | ادمین (JWT) |
| `/api/v1/portfolio` | عمومی |
| `/api/v1/ticket-template` | عمومی |
| `/api/v1/otp-channels` | عمومی |
| `/api/v1/site-content` | عمومی |
| `/api/v1/payment-info` | عمومی |
| `/api/v1/account/reservations` | مشتری (JWT) |
| `/api/v1/account/reservations/{id}/ticket\.pdf` | مشتری (JWT) |
| `/api/v1/account/messages` | مشتری (JWT) |
| `/api/v1/admin/messages` | ادمین (JWT) |
| `/api/v1/admin/messages/{id}` | ادمین (JWT) |
| `/api/v1/team` | عمومی |
| `/api/v1/team/{slug}` | عمومی |
| `/api/v1/admin/faqs` | ادمین (JWT) |

## POST

| مسیر | دسترسی |
|---|---|
| `/api/v1/admin/login` | ادمین (JWT) |
| `/api/v1/admin/refresh` | ادمین (JWT) |
| `/api/v1/reservations/{id}/receipt` | عمومی |
| `/api/v1/reservations` | عمومی |
| `/api/v1/admin/reservations/{id}/approve` | ادمین (JWT) |
| `/api/v1/admin/reservations/{id}/reject` | ادمین (JWT) |
| `/api/v1/admin/reservations/{id}/needs-correction` | ادمین (JWT) |
| `/api/v1/admin/waitlist/{id}/approve` | ادمین (JWT) |
| `/api/v1/admin/waitlist/{id}/reject` | ادمین (JWT) |
| `/api/v1/admin/bank-cards` | ادمین (JWT) |
| `/api/v1/admin/bank-cards/{id}/activate` | ادمین (JWT) |
| `/api/v1/admin/bank-cards/auto-rotate` | ادمین (JWT) |
| `/api/v1/admin/broadcasts` | ادمین (JWT) |
| `/api/v1/admin/reservations/bulk-approve` | ادمین (JWT) |
| `/api/v1/admin/portfolio` | ادمین (JWT) |
| `/api/v1/admin/payment-info` | ادمین (JWT) |
| `/api/v1/admin/events` | ادمین (JWT) |
| `/api/v1/admin/upload` | ادمین (JWT) |
| `/api/v1/admin/sessions` | ادمین (JWT) |
| `/api/v1/auth/customer/request-otp` | — |
| `/api/v1/auth/customer/verify-otp` | — |
| `/api/v1/auth/customer/refresh` | — |
| `/api/v1/account/messages` | مشتری (JWT) |
| `/api/v1/admin/messages/{id}` | ادمین (JWT) |
| `/api/v1/admin/team` | ادمین (JWT) |
| `/api/v1/admin/faqs` | ادمین (JWT) |
| `/api/v1/admin/tickets/verify` | ادمین (JWT) |
| `/api/v1/admin/tickets/checkin` | ادمین (JWT) |

## PATCH

| مسیر | دسترسی |
|---|---|
| `/api/v1/admin/events/{id}` | ادمین (JWT) |
| `/api/v1/admin/sessions/{id}` | ادمین (JWT) |
| `/api/v1/admin/portfolio/{id}` | ادمین (JWT) |
| `/api/v1/admin/team/{id}` | ادمین (JWT) |
| `/api/v1/admin/faqs/{id}` | ادمین (JWT) |
| `/api/v1/admin/settings` | ادمین (JWT) |
| `/api/v1/admin/ticket-template` | ادمین (JWT) |

## DELETE

| مسیر | دسترسی |
|---|---|
| `/api/v1/admin/events/{id}` | ادمین (JWT) |
| `/api/v1/admin/sessions/{id}` | ادمین (JWT) |
| `/api/v1/admin/portfolio/{id}` | ادمین (JWT) |
| `/api/v1/admin/team/{id}` | ادمین (JWT) |
| `/api/v1/admin/faqs/{id}` | ادمین (JWT) |
| `/api/v1/admin/bank-cards/{id}` | ادمین (JWT) |

---

> این فایل خودکار تولید می‌شود (`python3 docs/generate.py`). برای توضیح رفتار هر اندپوینت، خود `bot/api/server.py` را بخوان — پرکامنت است و دلیل تصمیم‌ها کنار کد نوشته شده.
