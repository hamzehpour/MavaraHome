"""Real SMTP email sending for customer OTP codes (Schema v9 rewrite:
email replaces the old phone+Telegram-delivery login flow — this project
has no SMS provider, and routing every login through the Telegram bot
just to receive a code required a one-time "connect Telegram" step;
email needs no such indirection).

Configured entirely via .env (SMTP_HOST/PORT/USER/PASS/FROM — see
config/settings.py and .env.example). If SMTP_HOST is empty (nothing
configured yet, e.g. local testing), falls back to printing the email to
the console/log instead of failing — same "works locally without real
credentials" philosophy the project already uses for BOT_TOKEN (see
README's testing guide, and seed_phase4_8.py which relies on exactly
this fallback to print a usable OTP code without a real mail server).
"""
import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from config.settings import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_FROM_NAME, SMTP_USE_TLS,
)

logger = logging.getLogger("mavara_bot")


def send_email(*, to: str, subject: str, body: str,
               attachments: list[tuple[str, bytes]] | None = None) -> bool:
    """Best-effort send. Returns True if the email was sent (or, with no
    SMTP configured, printed) — False only on an actual send failure
    against a configured SMTP server, so callers can decide whether to
    surface an error to the user.

    attachments: optional list of (filename, content_bytes) — e.g. the
    approval email's PDF ticket (see reservation_service.
    _build_ticket_pdf_bytes()). Every attachment is sent as application/
    pdf; nothing here needs any other type yet, so this isn't a general
    MIME-type parameter — add one if that changes."""
    if not SMTP_HOST:
        logger.info("SMTP not configured — printing email instead of sending. To=%s Subject=%s", to, subject)
        attachment_note = f" (+{len(attachments)} attachment(s): {', '.join(a[0] for a in attachments)})" if attachments else ""
        print(
            f"\n===== EMAIL (SMTP not configured — set SMTP_HOST in .env for real delivery) =====\n"
            f"To: {to}\nSubject: {subject}{attachment_note}\n\n{body}\n"
            f"====================================================================================\n"
        )
        return True

    # Plain MIMEText when there's nothing to attach (the overwhelming
    # majority of calls — OTP codes, rejection notices) rather than
    # always building a multipart message; keeps every existing email
    # exactly the same wire format it always was.
    if attachments:
        msg = MIMEMultipart()
        msg.attach(MIMEText(body, "plain", "utf-8"))
        for filename, content in attachments:
            part = MIMEApplication(content, _subtype="pdf")
            part.add_header("Content-Disposition", "attachment", filename=filename)
            msg.attach(part)
    else:
        msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr((SMTP_FROM_NAME, SMTP_FROM or SMTP_USER))
    msg["To"] = to

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            if SMTP_USE_TLS:
                server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM or SMTP_USER, [to], msg.as_string())
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False
