"""Phase 6 — web-downloadable PDF ticket, with real Persian typesetting.

Uses reportlab (see requirements.txt) to lay out a print-friendly, RTL
ticket embedding the SAME signed QR payload the Telegram bot already
sends (utils/qr_signing.sign_code), so a single admin verification
endpoint (POST /api/v1/admin/tickets/verify) works for both a
phone-screenshot from the bot AND a printed/downloaded web PDF.

Persian text handling
----------------------
reportlab has no built-in RTL/glyph-joining support, so on its own it
would draw Persian letters unjoined and left-to-right (unreadable). This
module fixes that properly instead of falling back to English:

 1. Vazirmatn (already the site's own font, assets/fonts/*.ttf — same
    family used by the website) is embedded via reportlab's TTFont, so
    Persian glyphs actually exist in the output PDF.
 2. Every piece of Persian text is passed through
    utils.persian_text.shape_fa(), which joins letters into their correct
    contextual form and reorders the string into visual order (see that
    module's docstring) before any drawString/drawRightString call.
 3. Layout is right-to-left: the right margin is the anchor, event title
    and every label/value line are right-aligned, and long text (address,
    admin-entered notes) is word-wrapped against that same right margin.
 4. Numbers people actually read (seat count, price) are rendered in
    Persian digits, matching how a real Persian ticket looks. The
    reservation code and QR payload are deliberately left in plain ASCII
    — they're identifiers meant to be typed/scanned/read over the phone
    to support, not prose.

Ticket template (admin-editable)
---------------------------------
Header title/subtitle/footer text and an optional logo come from
services.settings_service.get_ticket_template() (edited from the
website's pages/admin/ticket-template.html). A specific event can also
override the header logo (events.ticket_logo) and adds its own
`important_notes` (free text, one consideration per line — e.g. parking
instructions, "please keep silent") which is printed automatically under
a "ملاحظات" heading — see services.ticket_service.get_ticket_context()
for how these are gathered per-reservation.
"""
import io
import os

from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from utils.qr_generator import generate_qr_image_bytes
from utils.qr_signing import sign_code
from utils.persian_text import shape_fa
from utils.jalali import to_persian_digits

NAVY = HexColor("#1b2340")
GOLD = HexColor("#c8a24a")
INK = HexColor("#1b2340")
MUTED = HexColor("#6b6f80")
FAINT_LINE = HexColor("#e4e2da")

_FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")

FONT_REGULAR = "Vazirmatn"
FONT_MEDIUM = "Vazirmatn-Medium"
FONT_SEMIBOLD = "Vazirmatn-SemiBold"
FONT_BOLD = "Vazirmatn-Bold"

_FALLBACK_FONT = "Helvetica"
_FALLBACK_FONT_BOLD = "Helvetica-Bold"
_fonts_registered = False
_fonts_available = False


def _register_fonts() -> bool:
    """Registers the Vazirmatn family with reportlab exactly once. Returns
    whether real Persian-capable fonts are available — if the .ttf files
    are somehow missing (e.g. a stripped deployment), every caller below
    falls back to Helvetica instead of crashing ticket generation; Persian
    text will render as boxes in that case, but a ticket still comes out."""
    global _fonts_registered, _fonts_available
    if _fonts_registered:
        return _fonts_available
    _fonts_registered = True
    mapping = {
        FONT_REGULAR: "Vazirmatn-Regular.ttf",
        FONT_MEDIUM: "Vazirmatn-Medium.ttf",
        FONT_SEMIBOLD: "Vazirmatn-SemiBold.ttf",
        FONT_BOLD: "Vazirmatn-Bold.ttf",
    }
    try:
        for font_name, filename in mapping.items():
            pdfmetrics.registerFont(TTFont(font_name, os.path.join(_FONTS_DIR, filename)))
        _fonts_available = True
    except Exception:
        import logging
        logging.getLogger("mavara_bot").exception(
            "Could not load Vazirmatn fonts from %s — ticket PDFs will fall "
            "back to Helvetica (Persian text will not render).", _FONTS_DIR
        )
        _fonts_available = False
    return _fonts_available


def _f(name: str) -> str:
    """Resolves a Vazirmatn font name to itself if fonts loaded OK, else
    to the closest Helvetica fallback (bold family stays bold)."""
    if _register_fonts():
        return name
    return _FALLBACK_FONT_BOLD if name in (FONT_SEMIBOLD, FONT_BOLD) else _FALLBACK_FONT


def _wrap_fa(c: canvas.Canvas, text: str, font: str, size: float, max_width: float) -> list[str]:
    """Word-wraps `text` (raw, unshaped Persian) against max_width,
    returning already-shaped lines ready to draw. Re-shapes each growing
    line from scratch rather than shaping word-by-word and concatenating
    — letter joining depends on neighbours, so shaping fragments
    separately can produce the wrong glyph forms at the seams."""
    words = str(text).split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = current + [word]
        shaped_trial = shape_fa(" ".join(trial))
        if not current or c.stringWidth(shaped_trial, font, size) <= max_width:
            current = trial
        else:
            lines.append(shape_fa(" ".join(current)))
            current = [word]
    if current:
        lines.append(shape_fa(" ".join(current)))
    return lines or [""]


def build_ticket_pdf(*, reservation: dict, event_title: str, session_date_display: str,
                      session_time: str, address: str | None,
                      important_notes: str | None = None,
                      logo_path: str | None = None,
                      template: dict | None = None) -> bytes:
    """reservation must include: reservation_code, people, total_price,
    attendee_name (or buyer name passed in already). Raises ValueError if
    reservation has no reservation_code yet (ticket not issued).

    important_notes: raw admin-entered text, one consideration per line
        (e.g. "جای پارک نیست، لطفاً بالاتر پارک کنید"), printed under a
        "ملاحظات" heading. May be None/empty — the section is simply
        omitted.
    logo_path: resolved filesystem path to an image to show in the header
        (event-specific override, or the template's default). May be
        None/missing/unreadable — the header just shows text in that case.
    template: {"title", "subtitle", "footer"} — see
        services.settings_service.get_ticket_template(). Falls back to
        sane defaults if not given.
    """
    code = reservation.get("reservation_code")
    if not code:
        raise ValueError("reservation has no reservation_code — ticket not issued yet")

    template = template or {}
    tmpl_title = template.get("title") or "خانه ماورا"
    tmpl_subtitle = template.get("subtitle") or "بلیت الکترونیک"
    tmpl_footer = template.get("footer") or (
        "این بلیت را همراه داشته باشید و QR آن را دم در نشان دهید — فقط برای یک نفر معتبر است."
    )

    qr_bytes = generate_qr_image_bytes(sign_code(code))
    qr_img = ImageReader(io.BytesIO(qr_bytes))

    buf = io.BytesIO()
    width, height = A5
    c = canvas.Canvas(buf, pagesize=A5)
    c.setTitle(f"Ticket {code}")

    right_margin = width - 15 * mm
    left_margin = 15 * mm
    content_width = right_margin - left_margin

    # ---- Header band ----
    header_h = 34 * mm
    c.setFillColor(NAVY)
    c.rect(0, height - header_h, width, header_h, fill=1, stroke=0)

    # If a logo is set, let it carry the branding on its own (many logos
    # are full wordmark lockups, not bare emblems — drawing our own big
    # title text underneath would duplicate/collide with text already
    # baked into the image). A small white card behind it keeps it
    # legible on the navy band regardless of whether the source image has
    # its own opaque background or a transparent one.
    logo_drawn = False
    logo_size = 14 * mm
    card_size = logo_size + 5 * mm
    card_top_gap = 5 * mm
    if logo_path and os.path.isfile(logo_path):
        try:
            card_x = width / 2 - card_size / 2
            card_y = height - card_top_gap - card_size
            c.setFillColor(HexColor("#ffffff"))
            c.roundRect(card_x, card_y, card_size, card_size, 3 * mm, fill=1, stroke=0)
            c.drawImage(
                ImageReader(logo_path),
                width / 2 - logo_size / 2, card_y + (card_size - logo_size) / 2,
                logo_size, logo_size,
                mask="auto", preserveAspectRatio=True, anchor="c",
            )
            logo_drawn = True
        except Exception:
            logo_drawn = False

    if logo_drawn:
        c.setFillColor(HexColor("#ffffff"))
        c.setFont(_f(FONT_REGULAR), 9)
        subtitle_y = height - card_top_gap - card_size - 3 * mm
        c.drawCentredString(width / 2, subtitle_y, shape_fa(tmpl_subtitle))
    else:
        title_y = height - 14 * mm
        c.setFillColor(GOLD)
        c.setFont(_f(FONT_BOLD), 15)
        c.drawCentredString(width / 2, title_y, shape_fa(tmpl_title))
        c.setFillColor(HexColor("#ffffff"))
        c.setFont(_f(FONT_REGULAR), 9)
        c.drawCentredString(width / 2, title_y - 7 * mm, shape_fa(tmpl_subtitle))

    y = height - header_h - 12 * mm

    # ---- Event title ----
    c.setFillColor(INK)
    c.setFont(_f(FONT_BOLD), 14)
    for line in _wrap_fa(c, event_title or "-", _f(FONT_BOLD), 14, content_width):
        c.drawRightString(right_margin, y, line)
        y -= 7 * mm
    y -= 2 * mm

    c.setStrokeColor(FAINT_LINE)
    c.setLineWidth(0.6)
    c.line(left_margin, y, right_margin, y)
    y -= 8 * mm

    # ---- Info rows (label + value on one right-aligned, bidi-correct line) ----
    people = reservation.get("people", 0)
    total_price = reservation.get("total_price", 0)
    rows = [
        ("تاریخ", session_date_display or "-"),
        ("ساعت", session_time or "-"),
        ("تعداد نفرات", to_persian_digits(str(people))),
        ("به نام", reservation.get("attendee_name") or "-"),
        ("مبلغ پرداختی", f"{to_persian_digits(f'{total_price:,}')} تومان"),
        ("کد رزرو", code),  # left as-is: an ASCII identifier, not prose
    ]
    c.setFont(_f(FONT_REGULAR), 10.5)
    for label, value in rows:
        c.setFillColor(MUTED)
        c.setFont(_f(FONT_MEDIUM), 9.5)
        c.drawRightString(right_margin, y, shape_fa(f"{label}"))
        c.setFillColor(INK)
        c.setFont(_f(FONT_REGULAR), 10.5)
        # Reservation code stays LTR/unshaped (it's an ASCII id like
        # "MV-AB12CD"); everything else is Persian and needs shaping.
        value_text = value if label == "کد رزرو" else shape_fa(value)
        c.drawRightString(right_margin - 34 * mm, y, value_text)
        y -= 7.2 * mm

    if address:
        c.setFillColor(MUTED)
        c.setFont(_f(FONT_MEDIUM), 9.5)
        c.drawRightString(right_margin, y, shape_fa("آدرس"))
        y -= 6.2 * mm
        c.setFillColor(INK)
        c.setFont(_f(FONT_REGULAR), 10)
        for line in _wrap_fa(c, address, _f(FONT_REGULAR), 10, content_width):
            c.drawRightString(right_margin, y, line)
            y -= 6.2 * mm
        y -= 1 * mm

    # ---- Important notes / ملاحظات (admin-entered, per event) ----
    note_lines = [n.strip() for n in (important_notes or "").splitlines() if n.strip()]
    if note_lines:
        y -= 3 * mm
        c.setStrokeColor(FAINT_LINE)
        c.line(left_margin, y, right_margin, y)
        y -= 7 * mm
        c.setFillColor(GOLD)
        c.setFont(_f(FONT_SEMIBOLD), 10.5)
        c.drawRightString(right_margin, y, shape_fa("ملاحظات"))
        y -= 7 * mm
        c.setFont(_f(FONT_REGULAR), 9.5)
        bullet_r = 0.7 * mm
        text_right = right_margin - 4.5 * mm
        for note in note_lines:
            wrapped = _wrap_fa(c, note, _f(FONT_REGULAR), 9.5, content_width - 5 * mm)
            c.setFillColor(GOLD)
            c.circle(right_margin - 1.5 * mm, y - 1.6 * mm, bullet_r, fill=1, stroke=0)
            c.setFillColor(INK)
            for i, line in enumerate(wrapped):
                c.drawRightString(text_right, y, line)
                y -= 5.6 * mm
            y -= 1 * mm

    # ---- QR + footer ----
    qr_size = 42 * mm
    qr_y = 12 * mm
    c.drawImage(qr_img, left_margin, qr_y, qr_size, qr_size)

    footer_text_right = right_margin
    footer_max_width = content_width - qr_size - 6 * mm
    fy = qr_y + qr_size - 5 * mm
    c.setFillColor(MUTED)
    c.setFont(_f(FONT_REGULAR), 8)
    for line in _wrap_fa(c, tmpl_footer, _f(FONT_REGULAR), 8, footer_max_width):
        c.drawRightString(footer_text_right, fy, line)
        fy -= 4.6 * mm

    c.showPage()
    c.save()
    return buf.getvalue()
