"""
Pure-Python Gregorian <-> Jalali (Persian/Shamsi) calendar conversion.
No external dependency (jdatetime is not installable in this offline
build environment) — this implements the standard, widely-used 33-year
cycle algorithm (the same math used by the jdatetime/jalaali-js
libraries), accurate for any date from 1178 to well past 1500 SH.
"""
from datetime import date

WEEKDAY_NAMES_FA = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]
MONTH_NAMES_FA = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"


def to_persian_digits(s: str) -> str:
    return "".join(_PERSIAN_DIGITS[int(ch)] if ch.isdigit() else ch for ch in s)


def _div(a: int, b: int) -> int:
    return a // b


def gregorian_to_jalali(g_year: int, g_month: int, g_day: int) -> tuple[int, int, int]:
    g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gy = g_year - 1600
    gm = g_month - 1
    gd = g_day - 1

    g_day_no = 365 * gy + _div(gy + 3, 4) - _div(gy + 99, 100) + _div(gy + 399, 400)
    for i in range(gm):
        g_day_no += g_days_in_month[i]
    if gm > 1 and ((g_year % 4 == 0 and g_year % 100 != 0) or (g_year % 400 == 0)):
        g_day_no += 1
    g_day_no += gd

    j_day_no = g_day_no - 79

    j_np = _div(j_day_no, 12053)
    j_day_no %= 12053

    jy = 979 + 33 * j_np + 4 * _div(j_day_no, 1461)
    j_day_no %= 1461

    if j_day_no >= 366:
        jy += _div(j_day_no - 1, 365)
        j_day_no = (j_day_no - 1) % 365

    j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
    jm = 0
    for i in range(11):
        if j_day_no < j_days_in_month[i]:
            jm = i
            break
        j_day_no -= j_days_in_month[i]
        jm = i + 1
    jd = j_day_no + 1

    return jy, jm + 1, jd


def jalali_to_gregorian(j_year: int, j_month: int, j_day: int) -> tuple[int, int, int]:
    jy = j_year - 979
    jm = j_month - 1
    jd = j_day - 1

    j_day_no = 365 * jy + _div(jy, 33) * 8 + _div(jy % 33 + 3, 4)
    j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
    for i in range(jm):
        j_day_no += j_days_in_month[i]
    j_day_no += jd

    g_day_no = j_day_no + 79

    gy = 1600 + 400 * _div(g_day_no, 146097)
    g_day_no %= 146097

    leap = True
    if g_day_no >= 36525:
        g_day_no -= 1
        gy += 100 * _div(g_day_no, 36524)
        g_day_no %= 36524
        if g_day_no >= 365:
            g_day_no += 1
        else:
            leap = False

    gy += 4 * _div(g_day_no, 1461)
    g_day_no %= 1461

    if g_day_no >= 366:
        leap = False
        g_day_no -= 1
        gy += _div(g_day_no, 365)
        g_day_no %= 365

    g_days_in_month = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    for i in range(12):
        if g_day_no < g_days_in_month[i]:
            gm = i
            break
        g_day_no -= g_days_in_month[i]
        gm = i + 1
    gd = g_day_no + 1

    return gy, gm + 1, gd


def today_jalali() -> tuple[int, int, int]:
    t = date.today()
    return gregorian_to_jalali(t.year, t.month, t.day)


def gregorian_iso_to_jalali_display(iso_date: str) -> str:
    """'2026-08-01' -> 'شنبه ۱۰ مرداد ۱۴۰۵' (weekday + day + month + year, Persian digits)."""
    y, m, d = (int(x) for x in iso_date.split("-"))
    jy, jm, jd = gregorian_to_jalali(y, m, d)
    gdate = date(y, m, d)
    weekday_fa = WEEKDAY_NAMES_FA[gdate.weekday()]
    return to_persian_digits(f"{weekday_fa} {jd} {MONTH_NAMES_FA[jm - 1]} {jy}")


def gregorian_iso_to_gregorian_display(iso_date: str) -> str:
    """For events explicitly configured to show the Gregorian calendar to
    buyers (e.g. an event held outside Iran) — 'Saturday, August 1, 2026'."""
    y, m, d = (int(x) for x in iso_date.split("-"))
    gdate = date(y, m, d)
    weekday_en = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][gdate.weekday()]
    month_en = ["January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December"][m - 1]
    return f"{weekday_en}, {month_en} {d}, {y}"


def display_date_for_event(iso_date: str, calendar_type: str) -> str:
    """Single entry point used everywhere a date is shown to a buyer —
    respects the event's chosen calendar (jalali/gregorian) instead of
    always assuming Jalali. Falls back to Jalali for any unrecognized value."""
    if calendar_type == "gregorian":
        return gregorian_iso_to_gregorian_display(iso_date)
    return gregorian_iso_to_jalali_display(iso_date)


def jalali_ymd_to_iso(jy: int, jm: int, jd: int) -> str:
    gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
    return f"{gy:04d}-{gm:02d}-{gd:02d}"
