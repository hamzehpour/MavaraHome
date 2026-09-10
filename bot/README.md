# bot/ — بک‌اند خانه ماورا

> ## ⚠️ این فایل بازنشسته شده
>
> محتوای قبلی این فایل (۸۸۰ خط) به `docs/` منتقل شده و **بخش‌هایی از آن
> غلط شده بود** — مهم‌تر از همه، ماشین وضعیت رزرو را با وضعیت بازنشسته‌ی
> `awaiting_buyer_confirmation` به‌عنوان طراحی فعلی توصیف می‌کرد. هر کسی
> که برای دیباگ رزرو به آن مراجعه می‌کرد، گمراه می‌شد.
>
> **مرجع معتبر حالا این‌هاست:**
>
> | چه می‌خواهی | کجا |
> |---|---|
> | نقشه‌ی کل مستندات | [`../docs/README.md`](../docs/README.md) |
> | قواعد کار روی کد (اول این را بخوان) | [`../AGENTS.md`](../AGENTS.md) |
> | معماری، دو پروسه، تصمیم‌های فنی | [`../docs/02-architecture.md`](../docs/02-architecture.md) |
> | جدول‌ها و **ماشین وضعیت رزرو** | [`../docs/03-data-model.md`](../docs/03-data-model.md) |
> | عیب‌یابی | [`../docs/09-troubleshooting.md`](../docs/09-troubleshooting.md) |
> | دیپلوی | [`DEPLOYMENT.md`](DEPLOYMENT.md) |
> | تاریخچه‌ی کامل تغییرات | [`../CHANGELOG.md`](../CHANGELOG.md) |
>
> بخش‌های «نسخه ۳ تا ۱۱.۱» که قبلاً اینجا بودند، همان چیزی را می‌گفتند که
> `CHANGELOG.md` کامل‌تر و به‌روزتر دارد. متن کامل قدیمی در تاریخچه‌ی گیت
> باقی است.

## اجرای سریع

```bash
cd bot
python3 -m venv venv && source venv/bin/activate   # ویندوز: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # BOT_TOKEN و JWT_SECRET را پر کن
python3 migrate.py          # ساخت/به‌روزرسانی دیتابیس
python3 health_check.py     # باید ۱۱/۱۱ بدهد
python3 create_web_admin.py # ساخت حساب پنل وب

python3 bot.py              # پروسه‌ی ربات تلگرام
python3 -m api.server       # پروسه‌ی API (ترمینال دوم)
```

برای بالا آوردن سایت و API با هم روی یک پورت (فقط برای توسعه‌ی محلی):

```bash
STATIC_ROOT=../website python3 -m api.server   # http://127.0.0.1:8788
```

## تست

```bash
ENV=test python3 test_bot.py
```

هرگز به دیتابیس واقعی دست نمی‌زند: اگر `ENV=production` باشد بلافاصله خارج
می‌شود و در هر حالت روی یک فایل موقت کار می‌کند.
