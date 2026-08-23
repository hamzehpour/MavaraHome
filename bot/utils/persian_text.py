"""Persian/Arabic-script text shaping for PDF rendering.

reportlab (used by utils/ticket_pdf.py) draws glyphs exactly as given —
it has no idea that Persian letters must be *joined* into the correct
contextual form (isolated/initial/medial/final) depending on their
neighbours, and no idea that the overall line needs to run
right-to-left. Handed raw Persian text, it draws each letter in its
isolated form, left-to-right, which is unreadable.

The standard fix (the same one used by, e.g., WeasyPrint's PDF backend
without a real text-shaping engine, or any other reportlab-based Persian
document): `arabic_reshaper` first replaces each character with the
correctly-joined glyph for its context, then `bidi.algorithm.get_display`
reorders the whole string into "visual order" per the Unicode
Bidirectional Algorithm — after that, a plain left-to-right
`drawString`/`drawRightString` call renders it correctly, digits and all
(digits are weak-directional and keep reading left-to-right *within* the
surrounding right-to-left run, exactly like on a real printed ticket).
"""
import logging

logger = logging.getLogger("mavara_bot")

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _SHAPING_AVAILABLE = True
except ImportError:  # pragma: no cover — degrade instead of crashing PDF generation
    _SHAPING_AVAILABLE = False
    logger.warning(
        "arabic-reshaper / python-bidi not installed — Persian text in PDF "
        "tickets will render unshaped (unjoined letters). Run: "
        "pip install -r requirements.txt"
    )

_reshaper = arabic_reshaper.ArabicReshaper({
    "delete_harakat": False,
    "support_ligatures": True,
    "language": "Persian",
}) if _SHAPING_AVAILABLE else None


def shape_fa(text) -> str:
    """Reshape + bidi-reorder `text` for a plain LTR draw call. Safe to
    call on empty/None/already-Latin text — returns it unchanged (falls
    back to the raw string if the shaping libraries aren't installed, so
    a missing dependency degrades the ticket's look instead of crashing
    generation entirely)."""
    if not text:
        return ""
    text = str(text)
    if not _SHAPING_AVAILABLE:
        return text
    try:
        return get_display(_reshaper.reshape(text))
    except Exception:
        logger.exception("Persian shaping failed for %r — falling back to raw text", text)
        return text
