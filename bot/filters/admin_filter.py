from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from database.repositories import admins as admins_repo


class IsAdmin(BaseFilter):
    """
    Any staff member — owner, admin, or the limited 'operator'
    (phone-support) role. Use on handlers everyone on staff should reach:
    the pending-reservations queue, capacity lookups, manual/phone booking.
    """

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        return bool(user) and admins_repo.is_admin(user.id)


class IsFullAdmin(BaseFilter):
    """
    Owner/admin only — excludes 'operator'. Use on anything that changes
    project-wide configuration or structure: events/sessions management,
    settings, broadcast messages, staff management, data export.
    """

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        return bool(user) and admins_repo.is_full_admin(user.id)


class IsOwner(BaseFilter):
    """Owner only — for the most sensitive actions: setting the ownership
    passcode and adding/removing other owners."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        return bool(user) and admins_repo.get_role(user.id) == "owner"


class HasPermission(BaseFilter):
    """
    Fine-grained check against services/permissions.py — use this (instead
    of IsAdmin/IsFullAdmin) for anything that should be reachable by a
    specific permission group (finance/sales/content) even if that person
    isn't a full admin. Owner and full admin always pass every permission
    check, so existing setups with no groups configured keep working
    exactly as before.
    """

    def __init__(self, permission: str):
        self.permission = permission

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        from services import permissions
        user = event.from_user
        return bool(user) and permissions.staff_has_permission(user.id, self.permission)
