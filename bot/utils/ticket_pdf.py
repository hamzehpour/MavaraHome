"""Phase 6 — web-downloadable PDF ticket.

Uses reportlab (already available in this environment, unlike qrcode —
see requirements.txt) to lay out a simple, print-friendly ticket embedding
the SAME signed QR payload the Telegram bot already sends
(utils/qr_signing.sign_code), so a single admin verification endpoint
(POST /api/v1/admin/tickets/verify) works for both a phone-screenshot from
the bot AND a printed/downloaded web PDF — one QR format, not two.

NOTE for whoever deploys this: reportlab draws Latin text natively, but
this project's ticket content is Persian (RTL, joined Arabic-script
glyphs). reportlab has no built-in RTL/shaping support, so this module
keeps Persian labels on the LEFT as plain informational text (not
justified/shaped) with English/numeric fields (date-time, code, price
number) doing the visual heavy lifting — verified layout in this sandbox
with dummy data (see DEPLOYMENT.md "Phase 6 testing notes"); if true
shaped Persian typesetting is wanted later, the `arabic-reshaper` +
`python-bidi` libraries are the standard addition (not available in this
offline sandbox to install/verify).
"""
import io

from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from utils.qr_generator import generate_qr_image_bytes
from utils.qr_signing import sign_code

NAVY = HexColor("#1b2340")
GOLD = HexColor("#c8a24a")


def build_ticket_pdf(*, reservation: dict, event_title: str, session_date_display: str,
                      session_time: str, address: str | None) -> bytes:
    """reservation must include: reservation_code, people, total_price,
    attendee_name (or buyer name passed in already). Raises ValueError if
    reservation has no reservation_code yet (ticket not issued)."""
    code = reservation.get("reservation_code")
    if not code:
        raise ValueError("reservation has no reservation_code — ticket not issued yet")

    qr_bytes = generate_qr_image_bytes(sign_code(code))
    qr_img = ImageReader(io.BytesIO(qr_bytes))

    buf = io.BytesIO()
    width, height = A5
    c = canvas.Canvas(buf, pagesize=A5)

    # Header band
    c.setFillColor(NAVY)
    c.rect(0, height - 28 * mm, width, 28 * mm, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 14 * mm, "MAVARA HOME")
    c.setFillColor("white")
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, height - 21 * mm, "E-TICKET / بلیت الکترونیک")

    y = height - 40 * mm
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(15 * mm, y, event_title or "-")
    y -= 8 * mm

    rows = [
        ("Reservation code", code),
        ("Date", session_date_display or "-"),
        ("Time", session_time or "-"),
        ("Seats", str(reservation.get("people", "-"))),
        ("Attendee", reservation.get("attendee_name") or "-"),
        ("Total paid", f"{reservation.get('total_price', 0):,} Toman"),
    ]
    c.setFont("Helvetica", 10)
    for label, value in rows:
        c.setFillColor(HexColor("#666666"))
        c.drawString(15 * mm, y, f"{label}:")
        c.setFillColor(NAVY)
        c.drawString(55 * mm, y, str(value))
        y -= 7 * mm

    if address:
        c.setFillColor(HexColor("#666666"))
        c.drawString(15 * mm, y, "Address:")
        c.setFillColor(NAVY)
        c.drawString(55 * mm, y, address[:60])
        y -= 7 * mm

    qr_size = 45 * mm
    c.drawImage(qr_img, width - qr_size - 15 * mm, 15 * mm, qr_size, qr_size)
    c.setFont("Helvetica", 7)
    c.setFillColor(HexColor("#999999"))
    c.drawString(15 * mm, 10 * mm, "Show this QR at the door. Valid for one entry only.")

    c.showPage()
    c.save()
    return buf.getvalue()
