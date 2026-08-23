"""
Logs every incoming update (who, what) to both the file logger and the
`logs` DB table, and makes sure a blocked user can never proceed further.
This is the single place cross-cutting concerns like this belong —
handlers stay free of logging/blocking boilerplate.
"""
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from database.repositories import logs as logs_repo
from database.repositories import users as users_repo
from utils.logger import get_logger

logger = get_logger()


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)

        if user:
            if users_repo.is_blocked(user.id):
                if isinstance(event, CallbackQuery):
                    await event.answer("⛔️ دسترسی شما مسدود شده است.", show_alert=True)
                return None

            action = "message" if isinstance(event, Message) else "callback"
            payload = getattr(event, "text", None) or getattr(event, "data", None) or ""
            logger.info("%s from %s: %s", action, user.id, payload)
            logs_repo.record(action=action, telegram_id=user.id, details=str(payload)[:200])

        return await handler(event, data)
