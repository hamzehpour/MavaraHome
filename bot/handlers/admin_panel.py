from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from texts import fa
from filters.admin_filter import IsAdmin, IsFullAdmin
from states.admin_states import (
    AdminBroadcastStates, AdminSettingsStates, StaffManagementStates, DirectMessageStates,
)
from states.stats_states import StatsStates
from keyboards.admin import (
    admin_main_menu, staff_main_menu, settings_menu_keyboard,
    broadcast_confirm_keyboard, staff_list_actions_keyboard, staff_role_picker_keyboard,
)
from services import stats_service, settings_service, export_service, broadcast_service
from utils.safe_send import safe_answer
from database.repositories import users as users_repo
from database.repositories import admins as admins_repo
from database.repositories import logs as logs_repo

router = Router(name="admin_panel")


@router.message(Command("admin"), IsAdmin())
async def admin_home(message: Message) -> None:
    """Entry point for ALL staff — the menu shown depends on their role."""
    if admins_repo.is_full_admin(message.from_user.id):
        await message.answer(fa.ADMIN_MENU_TITLE, reply_markup=admin_main_menu())
    else:
        await message.answer(fa.STAFF_MENU_TITLE, reply_markup=staff_main_menu())


@router.callback_query(F.data == "admin:stats", IsFullAdmin())
async def show_stats(callback: CallbackQuery) -> None:
    from keyboards.admin import stats_event_keyboard
    await callback.message.answer("آمار فروش کدام رویداد را می‌خواهید؟", reply_markup=stats_event_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("stats_event:"), IsFullAdmin())
async def stats_pick_event(callback: CallbackQuery) -> None:
    from keyboards.admin import stats_period_keyboard
    event_id = int(callback.data.split(":", 1)[1])
    await callback.message.answer(fa.STATS_ASK_PERIOD, reply_markup=stats_period_keyboard(event_id))
    await callback.answer()


@router.callback_query(F.data.startswith("stats_period:"), IsFullAdmin())
async def stats_pick_period(callback: CallbackQuery, state: FSMContext) -> None:
    from keyboards.admin import calendar_keyboard, stats_result_keyboard
    from utils.jalali import today_jalali

    _, period, event_id_str = callback.data.split(":")
    event_id = int(event_id_str)
    if period == "custom":
        jy, jm, _ = today_jalali()
        await state.set_state(StatsStates.picking_from_date)
        await state.update_data(stats_event_id=event_id)
        await callback.message.edit_text(fa.STATS_ASK_CUSTOM_FROM, reply_markup=calendar_keyboard(jy, jm, "stats_from_cal"))
        await callback.answer()
        return

    date_from, date_to = stats_service.resolve_range(period)
    scope = None if event_id == 0 else event_id
    report = stats_service.get_range_report(date_from, date_to, event_id=scope)
    await callback.message.answer(
        fa.stats_range_report(report["totals"], report["by_session"]),
        reply_markup=stats_result_keyboard(date_from, date_to, event_id),
    )
    await callback.answer()


@router.callback_query(StatsStates.picking_from_date, F.data.startswith("stats_from_cal:nav:"), IsFullAdmin())
async def stats_from_nav(callback: CallbackQuery) -> None:
    from keyboards.admin import calendar_keyboard
    _, _, y, m = callback.data.split(":")
    await callback.message.edit_reply_markup(reply_markup=calendar_keyboard(int(y), int(m), "stats_from_cal"))
    await callback.answer()


@router.callback_query(StatsStates.picking_from_date, F.data == "stats_from_cal:back", IsFullAdmin())
async def stats_from_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()


@router.callback_query(StatsStates.picking_from_date, F.data.startswith("stats_from_cal:pick:"), IsFullAdmin())
async def stats_from_pick(callback: CallbackQuery, state: FSMContext) -> None:
    from keyboards.admin import calendar_keyboard
    from utils.jalali import today_jalali
    date_from = callback.data.split(":", 2)[2]
    await state.update_data(stats_from=date_from)
    await state.set_state(StatsStates.picking_to_date)
    jy, jm, _ = today_jalali()
    await callback.message.edit_text(fa.STATS_ASK_CUSTOM_TO, reply_markup=calendar_keyboard(jy, jm, "stats_to_cal"))
    await callback.answer()


@router.callback_query(StatsStates.picking_to_date, F.data.startswith("stats_to_cal:nav:"), IsFullAdmin())
async def stats_to_nav(callback: CallbackQuery) -> None:
    from keyboards.admin import calendar_keyboard
    _, _, y, m = callback.data.split(":")
    await callback.message.edit_reply_markup(reply_markup=calendar_keyboard(int(y), int(m), "stats_to_cal"))
    await callback.answer()


@router.callback_query(StatsStates.picking_to_date, F.data == "stats_to_cal:back", IsFullAdmin())
async def stats_to_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()


@router.callback_query(StatsStates.picking_to_date, F.data.startswith("stats_to_cal:pick:"), IsFullAdmin())
async def stats_to_pick(callback: CallbackQuery, state: FSMContext) -> None:
    from keyboards.admin import stats_result_keyboard
    date_to = callback.data.split(":", 2)[2]
    data = await state.get_data()
    date_from = data["stats_from"]
    event_id = data.get("stats_event_id", 0)
    await state.clear()

    scope = None if event_id == 0 else event_id
    report = stats_service.get_range_report(date_from, date_to, event_id=scope)
    await callback.message.edit_text(
        fa.stats_range_report(report["totals"], report["by_session"]),
        reply_markup=stats_result_keyboard(date_from, date_to, event_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("stats_contacts:"), IsFullAdmin())
async def stats_show_contacts(callback: CallbackQuery) -> None:
    _, date_from, date_to, event_id_str = callback.data.split(":")
    date_from = None if date_from == "-" else date_from
    date_to = None if date_to == "-" else date_to
    event_id = int(event_id_str)
    scope = None if event_id == 0 else event_id
    entries = stats_service.get_contact_list(date_from, date_to, event_id=scope)
    await callback.message.answer(fa.contact_list_report(entries))
    await callback.answer()


@router.callback_query(F.data == "admin:export", IsFullAdmin())
async def export_excel(callback: CallbackQuery, bot: Bot) -> None:
    buffer = export_service.export_reservations_xlsx()
    await bot.send_document(
        callback.from_user.id,
        document=BufferedInputFile(buffer.read(), filename="reservations_export.xlsx"),
        caption=fa.EXPORT_READY,
    )
    logs_repo.record("export_excel", callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "admin:export_logs", IsFullAdmin())
async def export_logs(callback: CallbackQuery, bot: Bot) -> None:
    buffer = export_service.export_logs_xlsx()
    await bot.send_document(
        callback.from_user.id,
        document=BufferedInputFile(buffer.read(), filename="audit_log_export.xlsx"),
        caption="📜 خروجی اکسل لاگ تغییرات آماده شد.",
    )
    logs_repo.record("export_logs", callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "admin:export_other", IsFullAdmin())
async def export_other_formats(callback: CallbackQuery, bot: Bot) -> None:
    csv_buffer = export_service.export_reservations_csv()
    json_buffer = export_service.export_reservations_json()
    await bot.send_document(
        callback.from_user.id,
        document=BufferedInputFile(csv_buffer.read(), filename="reservations_export.csv"),
    )
    await bot.send_document(
        callback.from_user.id,
        document=BufferedInputFile(json_buffer.read(), filename="reservations_export.json"),
        caption="📄 خروجی CSV و JSON آماده شد — فایل JSON برای اتصال سایت آینده مناسب است.",
    )
    logs_repo.record("export_csv_json", callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "admin:direct_message", IsFullAdmin())
async def direct_message_start(callback: CallbackQuery, state: FSMContext) -> None:
    from states.admin_states import DirectMessageStates
    await state.set_state(DirectMessageStates.awaiting_target)
    await callback.message.answer(fa.ASK_DIRECT_MESSAGE_TARGET)
    await callback.answer()


@router.message(DirectMessageStates.awaiting_target, IsFullAdmin())
async def direct_message_target(message: Message, state: FSMContext, bot: Bot) -> None:
    raw = message.text.strip()
    if raw.startswith("@"):
        try:
            chat = await bot.get_chat(raw)
            telegram_id = chat.id
        except Exception:
            await message.answer("❌ این یوزرنیم پیدا نشد. آیدی عددی را وارد کنید یا مطمئن شوید ربات را استارت کرده.")
            return
    elif raw.lstrip("-").isdigit():
        telegram_id = int(raw)
    else:
        await message.answer("❌ لطفاً یک آیدی عددی یا یوزرنیم با @ وارد کنید.")
        return

    await state.update_data(direct_message_target=telegram_id)
    await state.set_state(DirectMessageStates.awaiting_text)
    await message.answer(fa.ASK_DIRECT_MESSAGE_TEXT)


@router.message(DirectMessageStates.awaiting_text, IsFullAdmin())
async def direct_message_send(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    try:
        await bot.send_message(data["direct_message_target"], message.text)
        logs_repo.record("direct_message_sent", message.from_user.id, f"to={data['direct_message_target']}")
        await message.answer(fa.DIRECT_MESSAGE_SENT)
    except Exception:
        await message.answer(fa.DIRECT_MESSAGE_FAILED)


@router.callback_query(F.data == "admin:factory_reset", IsFullAdmin())
async def factory_reset_start(callback: CallbackQuery) -> None:
    from services import factory_reset_service
    from keyboards.admin import confirm_keyboard
    if not factory_reset_service.factory_reset_allowed():
        await callback.answer(fa.FACTORY_RESET_BLOCKED_PRODUCTION, show_alert=True)
        return
    await safe_answer(
        callback.message,
        fa.FACTORY_RESET_WARNING, parse_mode="Markdown",
        reply_markup=confirm_keyboard("factory_reset:confirmed", "noop"),
    )
    await callback.answer()


@router.callback_query(F.data == "factory_reset:confirmed", IsFullAdmin())
async def factory_reset_do(callback: CallbackQuery) -> None:
    from services import factory_reset_service
    if not factory_reset_service.factory_reset_allowed():
        await callback.answer(fa.FACTORY_RESET_BLOCKED_PRODUCTION, show_alert=True)
        return
    factory_reset_service.perform_factory_reset()
    logs_repo.record("factory_reset_performed", callback.from_user.id)
    await callback.message.answer(fa.FACTORY_RESET_DONE)
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast", IsFullAdmin())
async def broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    from keyboards.admin import broadcast_audience_keyboard
    await state.set_state(AdminBroadcastStates.choosing_audience)
    await callback.message.answer(fa.BROADCAST_ASK_AUDIENCE, reply_markup=broadcast_audience_keyboard())
    await callback.answer()


@router.callback_query(AdminBroadcastStates.choosing_audience, F.data.startswith("bc_aud:"), IsFullAdmin())
async def broadcast_pick_audience(callback: CallbackQuery, state: FSMContext) -> None:
    choice = callback.data.split(":", 1)[1]

    if choice in ("all", "seen", "not_seen"):
        await state.update_data(bc_target=choice)
        await state.set_state(AdminBroadcastStates.awaiting_message)
        await callback.message.answer(fa.ASK_BROADCAST_MESSAGE)
        await callback.answer()
        return

    # choice == "date" — need to pick an event, then a date, then day-vs-session
    from database.repositories import events as events_repo
    from keyboards.booking import events_keyboard
    events = events_repo.list_active_events()
    if not events:
        await callback.answer(fa.NO_ACTIVE_EVENTS, show_alert=True)
        return
    await state.set_state(AdminBroadcastStates.choosing_event_for_date)
    await callback.message.edit_text(fa.BROADCAST_PICK_EVENT, reply_markup=events_keyboard(events))
    await callback.answer()


@router.callback_query(AdminBroadcastStates.choosing_event_for_date, F.data.startswith("book_event:"), IsFullAdmin())
async def broadcast_pick_event(callback: CallbackQuery, state: FSMContext) -> None:
    from services import event_service
    from keyboards.booking import dates_keyboard
    event_id = int(callback.data.split(":", 1)[1])
    sessions = event_service.get_bookable_dates(event_id)
    if not sessions:
        await callback.answer(fa.NO_ACTIVE_EVENT, show_alert=True)
        return
    await state.update_data(bc_event_id=event_id)
    await state.set_state(AdminBroadcastStates.choosing_date_for_audience)
    await callback.message.edit_text(fa.BROADCAST_PICK_DATE, reply_markup=dates_keyboard(sessions, show_back=False))
    await callback.answer()


@router.callback_query(AdminBroadcastStates.choosing_date_for_audience, F.data.startswith("date:"), IsFullAdmin())
async def broadcast_pick_date(callback: CallbackQuery, state: FSMContext) -> None:
    from services import event_service
    from keyboards.admin import broadcast_session_or_day_keyboard
    date_iso = callback.data.split(":", 1)[1]
    data = await state.get_data()
    sessions = event_service.get_sessions_on_date(data["bc_event_id"], date_iso)
    await state.update_data(bc_date_iso=date_iso)
    await callback.message.edit_text(
        fa.BROADCAST_PICK_SESSION_OR_WHOLE_DAY,
        reply_markup=broadcast_session_or_day_keyboard(data["bc_event_id"], date_iso, sessions),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("bc_day:"), IsFullAdmin())
async def broadcast_pick_whole_day(callback: CallbackQuery, state: FSMContext) -> None:
    _, event_id, date_iso = callback.data.split(":")
    await state.update_data(bc_target="date", bc_event_id=int(event_id), bc_date_iso=date_iso)
    await state.set_state(AdminBroadcastStates.awaiting_message)
    await callback.message.answer(fa.ASK_BROADCAST_MESSAGE)
    await callback.answer()


@router.callback_query(F.data.startswith("bc_session:"), IsFullAdmin())
async def broadcast_pick_single_session(callback: CallbackQuery, state: FSMContext) -> None:
    session_id = int(callback.data.split(":", 1)[1])
    await state.update_data(bc_target="session", bc_session_id=session_id)
    await state.set_state(AdminBroadcastStates.awaiting_message)
    await callback.message.answer(fa.ASK_BROADCAST_MESSAGE)
    await callback.answer()


@router.message(AdminBroadcastStates.awaiting_message, IsFullAdmin())
async def broadcast_preview(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    target = data.get("bc_target", "all")
    audience = broadcast_service.resolve_audience(
        target,
        event_id=data.get("bc_event_id"),
        date_iso=data.get("bc_date_iso"),
        session_id=data.get("bc_session_id"),
    )
    await state.update_data(broadcast_text=message.text, bc_audience=audience)
    await state.set_state(AdminBroadcastStates.awaiting_confirm)
    await message.answer(fa.BROADCAST_CONFIRM.format(count=len(audience)), reply_markup=broadcast_confirm_keyboard())


@router.callback_query(AdminBroadcastStates.awaiting_confirm, F.data == "broadcast:send", IsFullAdmin())
async def broadcast_send(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    success, failed = await broadcast_service.broadcast(bot, data["broadcast_text"], data.get("bc_audience", []))
    logs_repo.record("broadcast_sent", callback.from_user.id, f"success={success} failed={failed}")
    await state.clear()
    await callback.message.answer(fa.BROADCAST_DONE.format(success=success, failed=failed))
    await callback.answer()


@router.callback_query(AdminBroadcastStates.awaiting_confirm, F.data == "broadcast:cancel", IsFullAdmin())
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("لغو شد.")
    await callback.answer()


@router.callback_query(F.data == "admin:settings", IsFullAdmin())
async def settings_menu(callback: CallbackQuery) -> None:
    await callback.message.answer(
        fa.SETTINGS_MENU_TITLE,
        reply_markup=settings_menu_keyboard(settings_service.EDITABLE_SETTINGS),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_setting:"), IsFullAdmin())
async def settings_edit_start(callback: CallbackQuery, state: FSMContext) -> None:
    key = callback.data.split(":", 1)[1]
    from database.repositories import settings as settings_repo
    current = settings_repo.get(key, "")
    label = settings_service.EDITABLE_SETTINGS.get(key, key)

    await state.update_data(setting_key=key)
    await state.set_state(AdminSettingsStates.awaiting_new_value)
    await callback.message.answer(fa.ASK_NEW_VALUE.format(label=label, current=current or "—"))
    await callback.answer()


@router.message(AdminSettingsStates.awaiting_new_value, IsFullAdmin())
async def settings_edit_save(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    settings_service.update_setting(data["setting_key"], message.text.strip())
    logs_repo.record("setting_updated", message.from_user.id, data["setting_key"])
    await state.clear()
    await message.answer(fa.SETTING_UPDATED)


# ---------------- staff (operator) management — owner/admin only ----------------

@router.callback_query(F.data == "admin:staff", IsFullAdmin())
async def staff_list(callback: CallbackQuery) -> None:
    from database.repositories import admin_groups as admin_groups_repo
    admins = admins_repo.list_admins()
    lines = [fa.staff_row(a["telegram_id"], a["role"], admin_groups_repo.get_groups(a["telegram_id"])) for a in admins]
    await callback.message.answer(
        fa.STAFF_LIST_TITLE + "\n\n" + "\n".join(lines),
        reply_markup=staff_list_actions_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "staff:manage_groups", IsFullAdmin())
async def manage_groups_pick_staff(callback: CallbackQuery) -> None:
    from keyboards.admin import pick_staff_for_groups_keyboard
    admins = admins_repo.list_admins()
    await callback.message.answer(fa.ASK_PICK_STAFF_FOR_GROUPS, reply_markup=pick_staff_for_groups_keyboard(admins))
    await callback.answer()


@router.callback_query(F.data.startswith("groups_pick:"), IsFullAdmin())
async def manage_groups_show(callback: CallbackQuery) -> None:
    from database.repositories import admin_groups as admin_groups_repo
    from keyboards.admin import toggle_groups_keyboard
    telegram_id = int(callback.data.split(":", 1)[1])
    current = admin_groups_repo.get_groups(telegram_id)
    await callback.message.answer(
        fa.manage_groups_header(telegram_id, current),
        reply_markup=toggle_groups_keyboard(telegram_id, current),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("groups_toggle:"), IsFullAdmin())
async def manage_groups_toggle(callback: CallbackQuery) -> None:
    from database.repositories import admin_groups as admin_groups_repo
    from keyboards.admin import toggle_groups_keyboard
    _, telegram_id_str, group_name = callback.data.split(":")
    telegram_id = int(telegram_id_str)

    current = admin_groups_repo.get_groups(telegram_id)
    if group_name in current:
        admin_groups_repo.remove_group(telegram_id, group_name)
        logs_repo.record("staff_group_removed", callback.from_user.id, f"{telegram_id}:{group_name}")
    else:
        admin_groups_repo.add_group(telegram_id, group_name)
        logs_repo.record("staff_group_added", callback.from_user.id, f"{telegram_id}:{group_name}")

    updated = admin_groups_repo.get_groups(telegram_id)
    await callback.message.edit_text(
        fa.manage_groups_header(telegram_id, updated),
        reply_markup=toggle_groups_keyboard(telegram_id, updated),
    )
    await callback.answer()


@router.callback_query(F.data == "staff:add", IsFullAdmin())
async def staff_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(StaffManagementStates.awaiting_new_staff_id)
    await callback.message.answer(fa.ASK_STAFF_TELEGRAM_ID)
    await callback.answer()


@router.message(StaffManagementStates.awaiting_new_staff_id, IsFullAdmin())
async def staff_add_id(message: Message, state: FSMContext, bot: Bot) -> None:
    raw = message.text.strip()

    if raw.startswith("@"):
        try:
            chat = await bot.get_chat(raw)
            telegram_id = chat.id
        except Exception:
            await message.answer(
                "❌ این یوزرنیم پیدا نشد. توجه کنید فرد باید حداقل یک بار ربات را استارت کرده باشد "
                "تا قابل‌شناسایی باشد — یا آیدی عددی‌اش را وارد کنید."
            )
            return
    elif raw.lstrip("-").isdigit():
        telegram_id = int(raw)
    else:
        await message.answer("❌ لطفاً یک آیدی عددی یا یوزرنیم با @ (مثل @username) وارد کنید.")
        return

    await state.update_data(new_staff_id=telegram_id)
    await state.set_state(StaffManagementStates.awaiting_new_staff_role)
    await message.answer(fa.ASK_STAFF_ROLE, reply_markup=staff_role_picker_keyboard())


@router.callback_query(StaffManagementStates.awaiting_new_staff_role, F.data.startswith("staff_role:"), IsFullAdmin())
async def staff_add_role(callback: CallbackQuery, state: FSMContext) -> None:
    role = callback.data.split(":", 1)[1]
    data = await state.get_data()
    admins_repo.add_admin(data["new_staff_id"], role=role)
    logs_repo.record("staff_added", callback.from_user.id, f"telegram_id={data['new_staff_id']} role={role}")
    await state.clear()
    await callback.message.answer(fa.STAFF_ADDED)
    await callback.answer()


@router.callback_query(F.data == "staff:remove", IsFullAdmin())
async def staff_remove_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(StaffManagementStates.awaiting_remove_staff_id)
    await callback.message.answer(fa.ASK_STAFF_TELEGRAM_ID)
    await callback.answer()


@router.message(StaffManagementStates.awaiting_remove_staff_id, IsFullAdmin())
async def staff_remove_id(message: Message, state: FSMContext, bot: Bot) -> None:
    raw = message.text.strip()
    if raw.startswith("@"):
        try:
            chat = await bot.get_chat(raw)
            telegram_id = chat.id
        except Exception:
            await message.answer("❌ این یوزرنیم پیدا نشد. آیدی عددی را وارد کنید.")
            return
    elif raw.lstrip("-").isdigit():
        telegram_id = int(raw)
    else:
        await message.answer("❌ لطفاً یک آیدی عددی یا یوزرنیم با @ وارد کنید.")
        return

    await state.clear()

    target_role = admins_repo.get_role(telegram_id)
    if target_role == "owner":
        # Removing an owner is protected: only another owner can even
        # start this, and it never happens instantly — see owner_service.
        if not admins_repo.is_admin(message.from_user.id) or admins_repo.get_role(message.from_user.id) != "owner":
            await message.answer("⛔️ فقط یک مالک می‌تواند مالک دیگری را حذف کند.")
            return

        from services import owner_service
        removal_at = owner_service.schedule_owner_removal(telegram_id)
        logs_repo.record("owner_removal_scheduled", message.from_user.id,
                          f"telegram_id={telegram_id} removal_at={removal_at}",
                          target_type="admin", target_id=telegram_id)

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=fa.OWNER_REMOVAL_CANCEL_BUTTON, callback_data=f"owner_removal_cancel:{telegram_id}")
        ]])
        await message.answer(fa.owner_removal_scheduled(24), reply_markup=cancel_kb)
        return

    admins_repo.remove_admin(telegram_id)
    from database.repositories import admin_groups as admin_groups_repo
    admin_groups_repo.remove_all_groups(telegram_id)
    logs_repo.record("staff_removed", message.from_user.id, f"telegram_id={telegram_id}",
                      target_type="admin", target_id=telegram_id)
    await message.answer(fa.STAFF_REMOVED)
