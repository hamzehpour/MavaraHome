"""
Shared helper for the 'edit in place' navigation pattern: instead of every
menu tap sending a new message (which stacks endlessly and buries old
buttons), we edit the current message's content. Falls back to deleting
the old message and sending a new one when the content type changes in a
way Telegram can't edit in place (e.g. going from a photo message to a
text menu), so navigation always ends up as a single current screen.
"""
from aiogram.types import CallbackQuery


async def go_to(callback: CallbackQuery, text: str, reply_markup=None, parse_mode: str | None = None) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return
    except Exception:
        pass  # message might be a photo, or content is identical, or too old to edit — fall through

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
