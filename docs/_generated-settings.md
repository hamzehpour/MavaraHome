<!-- این فایل به‌صورت خودکار از روی کد تولید شده است. دستی ویرایشش نکن.
     بازتولید:  python3 docs/generate.py  -->
# کلیدهای تنظیمات (تولید خودکار)

**64** کلید در جدول `settings` که ادمین می‌تواند از پنل وب یا از منوی تنظیمات ربات عوض کند — بدون دیپلوی. تعریف در `bot/services/settings_service.py`، گروه‌بندی صفحه‌ی پنل در آرایه‌ی `TABS` در `website/pages/admin/settings.html`.

| کلید | نوع | توضیح |
|---|---|---|
| `brand_name` | text | نام مجموعه |
| `welcome_message` | textarea | پیام خوش‌آمدگویی |
| `ticket_price` | int | قیمت پیش‌فرض بلیت (تومان) — فقط برای رویدادهایی که قیمت اختصاصی ندارند (قیمت هر رویداد را از صفحه «رویدادها… |
| `max_tickets_per_person` | int | حداکثر بلیت هر نفر |
| `rules_text` | textarea | متن قوانین |
| `support_contact` | text | شماره/آیدی پشتیبانی |
| `payment_expiry_minutes` | int | مهلت ارسال رسید توسط خریدار (دقیقه) — قفل ظرفیت تا این مدت باقی می‌ماند |
| `payment_reminder_minutes` | int | بعد از چند دقیقه از ایجاد رزرو، در صورت عدم ارسال رسید، ایمیل یادآوری ارسال شود (باید کمتر از «مهلت ارسال ر… |
| `tmpl_payment_instructions` | textarea | متن راهنمای پرداخت — متغیرها: {people} {unit_price} {total_price} {card_number} {card_holder} |
| `tmpl_receipt_received` | textarea | متن «رسید دریافت شد» — بدون متغیر خاص |
| `tmpl_ticket_confirmed` | textarea | متن نهایی بلیت (بعد از تأیید ادمین) — متغیرها: {event_title} {session_date_fa} {session_time} {people} {ful… |
| `tmpl_reservation_rejected` | textarea | متن «رد شدن پرداخت» — متغیر: {admin_note_block} |
| `tmpl_email_otp_subject` | text | موضوع ایمیل کد ورود — متغیرها: {brand_name} |
| `tmpl_email_otp_body` | textarea | متن ایمیل کد ورود — متغیرها: {code} {ttl_minutes} {brand_name} |
| `tmpl_email_approved_subject` | text | موضوع ایمیل تایید رزرو (رزرو عادی و تایید ظرفیت لیست انتظار، هر دو همین یکی) — متغیرها: {event_title} {bran… |
| `tmpl_email_approved_body` | textarea | متن ایمیل تایید رزرو — متغیرها: {event_title} {session_date} {session_time} {reservation_code} {brand_name} |
| `tmpl_email_rejected_subject` | text | موضوع ایمیل رد رزرو — متغیرها: {event_title} {brand_name} |
| `tmpl_email_rejected_body` | textarea | متن ایمیل رد رزرو — متغیرها: {event_title} {session_date} {reason_block} {brand_name} |
| `tmpl_email_waitlist_rejected_subject` | text | موضوع ایمیل «ظرفیتی آزاد نشد» (لیست انتظار) — متغیرها: {brand_name} |
| `tmpl_email_waitlist_rejected_body` | textarea | متن ایمیل «ظرفیتی آزاد نشد» (لیست انتظار) — متغیرها: {brand_name} |
| `tmpl_email_payment_reminder_subject` | text | موضوع ایمیل یادآوری پرداخت (وقتی رسید هنوز ارسال نشده) — متغیرها: {event_title} {brand_name} |
| `tmpl_email_payment_reminder_body` | textarea | متن ایمیل یادآوری پرداخت — متغیرها: {event_title} {minutes_remaining} {brand_name} |
| `tmpl_email_needs_correction_subject` | text | موضوع ایمیل «نیاز به اصلاح رسید» — متغیرها: {event_title} {brand_name} |
| `tmpl_email_needs_correction_body` | textarea | متن ایمیل «نیاز به اصلاح رسید» — متغیرها: {event_title} {correction_message} {brand_name} |
| `ticket_template_title` | text | عنوان بالای بلیت PDF (مثلاً نام مجموعه) |
| `ticket_template_subtitle` | text | زیرعنوان بالای بلیت PDF (مثلاً «بلیت الکترونیک») |
| `ticket_template_footer` | text | متن پایین بلیت PDF (زیر QR) |
| `otp_channels_enabled` | text | روش‌های ورود مشتری (با کاما جدا کنید — فقط email فعلاً واقعاً کار می‌کند، phone فقط زیرساختش آماده است، تا … |
| `content_hero_tagline` | text | شعار زیر عنوان اصلی صفحه اول |
| `content_quotes` | textarea | نقل‌قول‌های چرخشی صفحه اول — هر نقل‌قول در یک خط (حداکثر ۶ خط) |
| `content_resume_footer` | text | متن پایین صفحه‌ی رزومه (مشترک بین همه‌ی صفحات رزومه) |
| `content_about_p1` | textarea | متن «درباره خانه ماورا» — پاراگراف اول |
| `content_about_p2` | textarea | متن «درباره خانه ماورا» — پاراگراف دوم |
| `content_companion_p1` | textarea | متن «همراهی» — پاراگراف اول |
| `content_companion_p2` | textarea | متن «همراهی» — پاراگراف دوم |
| `content_companion_eyebrow` | text | زیرعنوان بالای صفحه «همراهی» |
| `content_companion_title` | text | عنوان اصلی صفحه «همراهی» |
| `content_companion_sub` | text | زیرعنوان صفحه «همراهی» |
| `content_companion_h3` | text | عنوان بالای لیست «این جلسات مناسب کسانی است که:» |
| `content_companion_li1` | text | آیتم اول لیست |
| `content_companion_li2` | text | آیتم دوم لیست |
| `content_companion_li3` | text | آیتم سوم لیست |
| `content_companion_li4` | text | آیتم چهارم لیست |
| `content_companion_note` | text | خط توضیح نحوه‌ی برگزاری |
| `content_companion_cta_text` | text | متن دکمه‌ی هماهنگی |
| `content_companion_cta_url` | text | لینک دکمه‌ی هماهنگی |
| `content_podcast_eyebrow` | text | زیرعنوان بالای صفحه «پادکست» |
| `content_podcast_title` | text | عنوان اصلی صفحه «پادکست» |
| `content_podcast_sub` | text | زیرعنوان صفحه «پادکست» |
| `content_podcast_intro` | textarea | پاراگراف معرفی پادکست (می‌تواند شامل <strong> باشد) |
| `content_podcast_castbox_url` | text | لینک کست‌باکس |
| `content_podcast_apple_url` | text | لینک اپل پادکست |
| `content_podcast_ig_desc` | text | آیدی اینستاگرام پادکست (نمایشی) |
| `content_podcast_ig_url` | text | لینک اینستاگرام پادکست |
| `content_podcast_support_eyebrow` | text | زیرعنوان بخش «حمایت» |
| `content_podcast_support_title` | text | عنوان بخش «حمایت» |
| `content_podcast_host` | text | خط «میزبان و سازنده» |
| `content_podcast_card_label` | text | برچسب شماره کارت |
| `content_podcast_card_number` | text | شماره کارت حمایت از پادکست |
| `content_footer_tagline` | text | شعار زیر لوگو در فوتر (می‌تواند شامل <br> برای شکست خط باشد) |
| `content_footer_copyright` | text | متن کپی‌رایت پایین فوتر |
| `content_contact_telegram` | text | آیدی تلگرام نمایش‌داده‌شده در صفحه تماس |
| `content_contact_instagram` | text | آیدی اینستاگرام نمایش‌داده‌شده در صفحه تماس |
| `content_location` | text | موقعیت مکانی (صفحه تماس و فوتر) |
