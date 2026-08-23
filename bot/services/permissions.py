"""
Central permission matrix. Every admin-only capability in the bot is named
here once; roles/groups are just named bundles of these. This is the
single source of truth — handlers and filters should check permissions
through has_permission(), never by comparing role strings directly (that
was the old owner/admin/operator-only model, kept working for backward
compatibility but now expressed as permission bundles too).
"""

# ---- individual permissions ----
APPROVE_PAYMENTS = "approve_payments"
MANUAL_BOOKING = "manual_booking"
VIEW_CAPACITY = "view_capacity"
VERIFY_TICKETS = "verify_tickets"
REQUEST_OVERFLOW_DECISION = "request_overflow_decision"  # receives overflow-approval prompts

MANAGE_EVENTS = "manage_events"
MANAGE_CHANNEL = "manage_channel"

MANAGE_BANK_CARDS = "manage_bank_cards"
VIEW_STATS = "view_stats"
EXPORT_DATA = "export_data"

MANAGE_SETTINGS = "manage_settings"
BROADCAST = "broadcast"
MANAGE_STAFF = "manage_staff"          # add/remove admin & operator (not owner)
MANAGE_OWNERSHIP = "manage_ownership"  # owner-only, never granted to a group

ALL_PERMISSIONS = {
    APPROVE_PAYMENTS, MANUAL_BOOKING, VIEW_CAPACITY, VERIFY_TICKETS, REQUEST_OVERFLOW_DECISION,
    MANAGE_EVENTS, MANAGE_CHANNEL, MANAGE_BANK_CARDS, VIEW_STATS, EXPORT_DATA,
    MANAGE_SETTINGS, BROADCAST, MANAGE_STAFF, MANAGE_OWNERSHIP,
}

# ---- role/group -> permission bundle ----
# 'owner' and 'admin' are intentionally not listed here — they're handled as
# "grants everything" (owner) / "everything except MANAGE_OWNERSHIP" (admin)
# in has_permission() below, so adding a new permission above never requires
# remembering to also add it to these two.
GROUP_PERMISSIONS = {
    "operator": {APPROVE_PAYMENTS, MANUAL_BOOKING, VIEW_CAPACITY, VERIFY_TICKETS},
    "finance": {MANAGE_BANK_CARDS, VIEW_STATS, EXPORT_DATA},
    "sales": {APPROVE_PAYMENTS, MANUAL_BOOKING, VIEW_CAPACITY, VERIFY_TICKETS, REQUEST_OVERFLOW_DECISION},
    "content": {MANAGE_EVENTS, MANAGE_CHANNEL},
}

# Human labels for the staff-management UI.
GROUP_LABELS = {
    "admin": "ادمین کامل",
    "operator": "پشتیبانی (محدود)",
    "finance": "مالی",
    "sales": "فروش",
    "content": "محتوا",
}


def permissions_for_roles(roles: set[str]) -> set[str]:
    """A staff member can hold more than one group at once — their
    effective permissions are the union of all their groups' bundles."""
    if "owner" in roles:
        return set(ALL_PERMISSIONS)
    if "admin" in roles:
        return ALL_PERMISSIONS - {MANAGE_OWNERSHIP}

    result: set[str] = set()
    for role in roles:
        result |= GROUP_PERMISSIONS.get(role, set())
    return result


def get_staff_roles(telegram_id: int) -> set[str]:
    from database.repositories import admins as admins_repo
    from database.repositories import admin_groups as admin_groups_repo

    base_role = admins_repo.get_role(telegram_id)
    if not base_role:
        return set()
    return {base_role} | admin_groups_repo.get_groups(telegram_id)


def get_staff_permissions(telegram_id: int) -> set[str]:
    return permissions_for_roles(get_staff_roles(telegram_id))


def staff_has_permission(telegram_id: int, permission: str) -> bool:
    return permission in get_staff_permissions(telegram_id)


def list_staff_with_permission(permission: str) -> list[int]:
    """Used for notification routing — e.g. only staff who can actually
    approve payments should get a 'new receipt uploaded' ping, not
    literally every admin regardless of what they're responsible for."""
    from database.repositories import admins as admins_repo
    return [
        admin["telegram_id"] for admin in admins_repo.list_admins()
        if staff_has_permission(admin["telegram_id"], permission)
    ]
