# Test Cases — سیستم رزرو

| # | سناریو | ورودی | نتیجه مورد انتظار |
|---|---|---|---|
| T1 | رزرو موفق | رویداد حُباب، سانس ۱۵:۳۰، ۲ نفر | کد MAV-XXXXXX + pending_payment + total = ۲×قیمت |
| T2 | ظرفیت پر | درخواست بیشتر از ظرفیت باقیمانده | خطای 409 sold_out |
| T3 | لیست انتظار | سانس تکمیل | status=waiting |
| T4 | آپلود رسید | تصویر ≤۱.۵MB | status=receipt_uploaded + پیام «رسید شما دریافت شد» |
| T5 | تصویر خراب/بزرگ | فایل >۱.۵MB | خطای receipt_too_large |
| T6 | شماره اشتباه/ناقص | بدون name/phone | خطای validation |
| T7 | رزرو تکراری | دو رزرو روی ظرفیت آخر | نفر دوم sold_out → waiting list |
| T8 | سانس حذفشده | سانس با status=deleted | خطای session_not_found |
| T9 | تایید ادمین | waiting_admin_confirmation → approved | وضعیت عوض + audit log |
| T10 | سانس تکراری (تقویم) | روز+ساعت تکراری | reject در سطح DB (unique) |

اجرا: `node tests/reservation.test.js`
