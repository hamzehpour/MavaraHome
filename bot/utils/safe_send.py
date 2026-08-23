"""Safe wrappers around aiogram's send/answer calls.

Root cause of the real bug reported: several messages in the reservation
flow (payment instructions, ticket confirmation, manual-booking confirm,
factory-reset warning) are built from admin-editable templates
(settings_service.render_*) and rendered with parse_mode="Markdown".
Telegram's legacy Markdown parser is extremely strict — a single unmatched
"_", "*", or "`" anywhere in the admin's template text OR in dynamic data
(e.g. a card holder name, an event title) makes Telegram reject the ENTIRE
message with TelegramBadRequest("can't parse entities..."). Because this
happened on the *payment instructions* message specifically, the reservation
FSM was left stuck in awaiting_receipt with no prompt ever shown to the
buyer, and no error surfaced to the admin either.

These helpers make that whole class of failure non-fatal: try to send with
the requested parse_mode, and if Telegram rejects it purely because of
formatting, log it and resend the *same text* as plain text instead of
losing the message (and the flow) entirely. A user should never see
"nothing happened" because an admin's template had one unbalanced
underscore.
"""
from aiogram.exceptions import TelegramBadRequest

from utils.logger import get_logger

logger = get_logger()


async def safe_answer(message, text: str, parse_mode: str | None = None, **kwargs):
    """Drop-in replacement for `message.answer(...)`."""
    try:
        return await message.answer(text, parse_mode=parse_mode, **kwargs)
    except TelegramBadRequest as exc:
        if "can't parse entities" not in str(exc):
            raise
        logger.warning("safe_answer: Markdown parse failed, resending as plain text: %s", exc)
        return await message.answer(text, parse_mode=None, **kwargs)


async def safe_send_message(bot, chat_id: int, text: str, parse_mode: str | None = None, **kwargs):
    """Drop-in replacement for `bot.send_message(...)`."""
    try:
        return await bot.send_message(chat_id, text, parse_mode=parse_mode, **kwargs)
    except TelegramBadRequest as exc:
        if "can't parse entities" not in str(exc):
            raise
        logger.warning("safe_send_message: Markdown parse failed for chat_id=%s, resending as plain text: %s", chat_id, exc)
        return await bot.send_message(chat_id, text, parse_mode=None, **kwargs)


async def safe_send_photo(bot, chat_id: int, photo, caption: str | None = None,
                           parse_mode: str | None = None, **kwargs):
    """Drop-in replacement for `bot.send_photo(...)`. On a Markdown parse
    failure in the caption, resends the same photo with the caption as
    plain text rather than losing the ticket/photo delivery entirely."""
    try:
        return await bot.send_photo(chat_id, photo, caption=caption, parse_mode=parse_mode, **kwargs)
    except TelegramBadRequest as exc:
        if "can't parse entities" not in str(exc):
            raise
        logger.warning("safe_send_photo: Markdown parse failed for chat_id=%s, resending as plain text: %s", chat_id, exc)
        return await bot.send_photo(chat_id, photo, caption=caption, parse_mode=None, **kwargs)
