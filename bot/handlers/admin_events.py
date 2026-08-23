from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from texts import fa
from filters.admin_filter import IsFullAdmin
from states.admin_states import AdminEventStates
from keyboards.admin import (
    events_menu_keyboard, event_detail_keyboard, session_detail_keyboard,
    confirm_keyboard, calendar_keyboard,
)
from database.repositories import events as events_repo
from database.repositories import sessions as sessions_repo
from database.repositories import reservations as reservations_repo
from database.repositories import logs as logs_repo
from validators.validators import is_positive_int, is_valid_time_hhmm, normalize_digits
from utils.jalali import today_jalali, gregorian_iso_to_jalali_display

router = Router(name="admin_events")
router.message.filter(IsFullAdmin())
router.callback_query.filter(IsFullAdmin())


@router.callback_query(F.data == "admin:events")
async def events_menu(callback: CallbackQuery) -> None:
    events = events_repo.list_all_events()
    await callback.message.answer(fa.EVENTS_MENU_TITLE, reply_markup=events_menu_keyboard(events))
    await callback.answer()


@router.callback_query(F.data == "admin_event:new")
async def new_event_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminEventStates.awaiting_event_title)
    await callback.message.answer(fa.ASK_EVENT_TITLE)
    await callback.answer()


@router.message(AdminEventStates.awaiting_event_title)
async def new_event_title(message: Message, state: FSMContext) -> None:
    from keyboards.admin import event_icon_keyboard
    await state.update_data(new_event_title=message.text.strip())
    await state.set_state(AdminEventStates.awaiting_event_icon)
    await message.answer("یک آیکن برای این رویداد انتخاب کنید:", reply_markup=event_icon_keyboard())


@router.callback_query(AdminEventStates.awaiting_event_icon, F.data.startswith("event_icon:"))
async def new_event_icon(callback: CallbackQuery, state: FSMContext) -> None:
    from keyboards.admin import calendar_type_keyboard
    icon = callback.data.split(":", 1)[1]
    await state.update_data(new_event_icon=icon)
    await state.set_state(AdminEventStates.awaiting_calendar_type)
    await callback.message.edit_text(
        "تقویمی که برای انتخاب تاریخ به مخاطب نشان داده شود کدام باشد؟\n"
        "(برای رویدادهای خارج از ایران، میلادی مناسب‌تر است)",
        reply_markup=calendar_type_keyboard(),
    )
    await callback.answer()


@router.callback_query(AdminEventStates.awaiting_calendar_type, F.data.startswith("event_cal_type:"))
async def new_event_calendar_type(callback: CallbackQuery, state: FSMContext) -> None:
    calendar_type = callback.data.split(":", 1)[1]
    data = await state.get_data()
    event_id = events_repo.create_event(
        title=data["new_event_title"], icon=data["new_event_icon"], calendar_type=calendar_type,
    )
    logs_repo.record("event_created", callback.from_user.id, f"event_id={event_id}")
    await state.clear()
    await callback.message.edit_text(fa.EVENT_CREATED)
    await callback.answer()


async def _render_event_detail(target, event_id: int) -> None:
    event = events_repo.get_event(event_id)
    if not event:
        return
    sessions = sessions_repo.list_sessions_for_event_admin(event_id)
    lines = [f"🎭 {event['title']} ({'فعال' if event['is_active'] else 'غیرفعال'})",
             f"📍 آدرس: {event.get('address') or 'ثبت نشده'}", ""]
    if not sessions:
        lines.append("هنوز سانسی برای این رویداد تعریف نشده.")
    if not event["is_active"]:
        from services import event_interest_service
        summary = event_interest_service.audience_summary(event_id)
        lines.append("")
        lines.append(f"👥 علاقه‌مندان اجرای بعدی: {summary['active']}")
        lines.append(f"🔔 اطلاع داده‌شده: {summary['notified']}")
        lines.append(f"🎟️ تبدیل به رزرو: {summary['converted']}")
    send = target.answer if hasattr(target, "answer") else target
    await send(
        "\n".join(lines),
        reply_markup=event_detail_keyboard(event_id, bool(event["is_active"]), sessions),
    )


@router.callback_query(F.data.startswith("admin_event:") & (F.data != "admin_event:new"))
async def event_detail(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])
    await _render_event_detail(callback.message, event_id)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_event_edit_address:"))
async def edit_address_start(callback: CallbackQuery, state: FSMContext) -> None:
    from keyboards.admin import confirm_keyboard
    event_id = int(callback.data.split(":")[1])
    event = events_repo.get_event(event_id)
    current = event.get("address") if event else None
    await state.update_data(edit_event_id=event_id)
    if current:
        await callback.message.answer(
            f"نشانی ثبت‌شده فعلی این است:\n\n{current}\n\nآیا می‌خواهید تغییرش دهید؟",
            reply_markup=confirm_keyboard(f"admin_event_edit_address_confirm:{event_id}", f"admin_event:{event_id}"),
        )
    else:
        await state.set_state(AdminEventStates.awaiting_event_address)
        await callback.message.answer(
            "آدرس کامل رویداد را وارد کنید — این آدرس داخل پیام نهایی بلیت برای خریدار نمایش داده می‌شود:"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_event_edit_address_confirm:"))
async def edit_address_confirmed(callback: CallbackQuery, state: FSMContext) -> None:
    event_id = int(callback.data.split(":")[1])
    await state.update_data(edit_event_id=event_id)
    await state.set_state(AdminEventStates.awaiting_event_address)
    await callback.message.answer("آدرس جدید را وارد کنید:")
    await callback.answer()


@router.message(AdminEventStates.awaiting_event_address)
async def edit_address_save(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    events_repo.update_address(data["edit_event_id"], message.text.strip())
    logs_repo.record("event_address_updated", message.from_user.id, f"event_id={data['edit_event_id']}")
    await state.clear()
    await message.answer("✅ آدرس رویداد ثبت شد.")
    await _render_event_detail(message, data["edit_event_id"])


@router.callback_query(F.data.startswith("admin_event_edit_calendar:"))
async def edit_calendar_type_start(callback: CallbackQuery) -> None:
    from keyboards.admin import calendar_type_edit_keyboard
    event_id = int(callback.data.split(":")[1])
    await callback.message.answer(
        "تقویمی که برای انتخاب تاریخ به مخاطب نشان داده شود کدام باشد؟",
        reply_markup=calendar_type_edit_keyboard(event_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("event_cal_type_edit:"))
async def edit_calendar_type_apply(callback: CallbackQuery) -> None:
    _, event_id_str, calendar_type = callback.data.split(":")
    event_id = int(event_id_str)
    events_repo.set_calendar_type(event_id, calendar_type)
    logs_repo.record("event_calendar_type_updated", callback.from_user.id,
                      f"event_id={event_id} -> {calendar_type}", target_type="event", target_id=event_id)
    await callback.message.answer("✅ نوع تقویم به‌روزرسانی شد.")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_event_toggle:"))
async def toggle_event_confirm(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])
    event = events_repo.get_event(event_id)
    action = "غیرفعال" if event["is_active"] else "فعال"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ بله، {action} کن", callback_data=f"admin_event_toggle_go:{event_id}")],
        [InlineKeyboardButton(text="⬅️ انصراف", callback_data=f"admin_event:{event_id}")],
    ])
    await callback.message.answer(f"آیا مطمئنید می‌خواهید رویداد «{event['title']}» را {action} کنید؟", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_event_toggle_go:"))
async def toggle_event(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])
    event = events_repo.get_event(event_id)
    was_active = bool(event["is_active"])
    events_repo.set_event_active(event_id, not was_active)
    logs_repo.record("event_toggled", callback.from_user.id, f"event_id={event_id}")

    if not was_active:
        # Paused → active: this is a reopening. Fan out to anyone who
        # registered "🔔 منتظر اجرای بعدی" interest — once per reopening,
        # not once per session, and never lets one blocked user stop the
        # rest (see event_interest_service.notify_event_reopened).
        from services import event_interest_service
        result = await event_interest_service.notify_event_reopened(callback.bot, event_id)
        if result["sent"] or result["failed"]:
            await callback.message.answer(
                f"🔔 اطلاع‌رسانی اجرای مجدد: {result['sent']} نفر مطلع شدند"
                + (f"، {result['failed']} مورد ناموفق." if result["failed"] else ".")
            )

    await _render_event_detail(callback.message, event_id)
    await callback.answer("✅ انجام شد.")


@router.callback_query(F.data.startswith("admin_event_delete_confirm:"))
async def confirm_delete_event(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])
    event = events_repo.get_event(event_id)
    await callback.message.answer(
        f"⚠️ آیا مطمئنید می‌خواهید رویداد «{event['title']}» و همه سانس‌ها/رزروهای آن را کامل حذف کنید؟\n"
        "این کار قابل بازگشت نیست.",
        reply_markup=confirm_keyboard(
            yes_callback=f"admin_event_delete_do:{event_id}",
            no_callback=f"admin_event:{event_id}",
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_event_delete_do:"))
async def delete_event(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])
    events_repo.delete_event(event_id)
    logs_repo.record("event_deleted", callback.from_user.id, f"event_id={event_id}")
    await callback.message.answer("🗑 رویداد حذف شد.")
    await callback.answer()


# ---------------- adding sessions (calendar → count → capacity → times) ----------------

@router.callback_query(F.data.startswith("admin_session_new:"))
async def new_session_calendar(callback: CallbackQuery, state: FSMContext) -> None:
    from keyboards.admin import any_calendar_keyboard
    from datetime import date as _date
    event_id = int(callback.data.split(":")[1])
    event = events_repo.get_event(event_id)
    calendar_type = (event.get("calendar_type") if event else "jalali") or "jalali"

    if calendar_type == "gregorian":
        today = _date.today()
        year, month = today.year, today.month
    else:
        year, month, _ = today_jalali()

    await state.update_data(new_session_event_id=event_id, session_calendar_type=calendar_type)
    await state.set_state(AdminEventStates.picking_session_date)
    prompt = "📅 Pick the day you want to define a session for:" if calendar_type == "gregorian" \
        else "📅 روزی که می‌خواهید سانس تعریف کنید را از تقویم انتخاب کنید:"
    await callback.message.edit_text(
        prompt, reply_markup=any_calendar_keyboard(year, month, "sess_cal", calendar_type),
    )
    await callback.answer()


@router.callback_query(AdminEventStates.picking_session_date, F.data.startswith("sess_cal:nav:"))
async def calendar_nav(callback: CallbackQuery, state: FSMContext) -> None:
    from keyboards.admin import any_calendar_keyboard
    data = await state.get_data()
    calendar_type = data.get("session_calendar_type", "jalali")
    _, _, y, m = callback.data.split(":")
    await callback.message.edit_reply_markup(
        reply_markup=any_calendar_keyboard(int(y), int(m), "sess_cal", calendar_type)
    )
    await callback.answer()


@router.callback_query(AdminEventStates.picking_session_date, F.data == "sess_cal:back")
async def calendar_back(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(None)
    await _render_event_detail(callback.message, data["new_session_event_id"])
    await callback.answer()


@router.callback_query(AdminEventStates.picking_session_date, F.data.startswith("sess_cal:pick:"))
async def calendar_pick(callback: CallbackQuery, state: FSMContext) -> None:
    from keyboards.admin import number_stepper_keyboard
    from utils.jalali import display_date_for_event
    data = await state.get_data()
    calendar_type = data.get("session_calendar_type", "jalali")
    iso_date = callback.data.split(":", 2)[2]
    await state.update_data(new_session_date=iso_date, session_count_value=1)
    await state.set_state(AdminEventStates.awaiting_session_count)
    await callback.message.edit_text(
        f"📅 روز انتخاب‌شده: {display_date_for_event(iso_date, calendar_type)}\n\n"
        "چند سانس برای این روز تعریف می‌کنید؟",
        reply_markup=number_stepper_keyboard(1, 1, 12, "sess_count", "سانس"),
    )
    await callback.answer()


@router.callback_query(AdminEventStates.awaiting_session_count, F.data.startswith("sess_count:"))
async def session_count_step(callback: CallbackQuery, state: FSMContext) -> None:
    from keyboards.admin import number_stepper_keyboard
    action = callback.data.split(":", 1)[1]
    data = await state.get_data()
    current = data.get("session_count_value", 1)

    if action == "inc":
        current = min(current + 1, 12)
    elif action == "dec":
        current = max(current - 1, 1)
    elif action == "confirm":
        await state.update_data(session_total=current, session_index=0, session_times=[])
        await state.set_state(AdminEventStates.awaiting_session_capacity)
        await callback.message.edit_text(
            fa.ASK_SESSION_CAPACITY,
            reply_markup=number_stepper_keyboard(10, 1, 500, "sess_cap", "نفر"),
        )
        await state.update_data(session_capacity_value=10)
        await callback.answer()
        return

    await state.update_data(session_count_value=current)
    await callback.message.edit_reply_markup(reply_markup=number_stepper_keyboard(current, 1, 12, "sess_count", "سانس"))
    await callback.answer()


@router.callback_query(AdminEventStates.awaiting_session_capacity, F.data.startswith("sess_cap:"))
async def session_capacity_step(callback: CallbackQuery, state: FSMContext) -> None:
    from keyboards.admin import number_stepper_keyboard
    action = callback.data.split(":", 1)[1]
    data = await state.get_data()
    current = data.get("session_capacity_value", 10)

    if action == "inc":
        current = min(current + 1, 500)
    elif action == "dec":
        current = max(current - 1, 1)
    elif action == "confirm":
        await state.update_data(session_capacity=current)
        await state.set_state(AdminEventStates.awaiting_session_time)
        await callback.message.edit_text(_ask_time_prompt(1, data["session_total"]))
        await callback.answer()
        return

    await state.update_data(session_capacity_value=current)
    await callback.message.edit_reply_markup(reply_markup=number_stepper_keyboard(current, 1, 500, "sess_cap", "نفر"))
    await callback.answer()


def _ask_time_prompt(index: int, total: int) -> str:
    return f"🕒 ساعت سانس شماره {index} از {total} را وارد کنید (مثال: 18:30):"


@router.message(AdminEventStates.awaiting_session_time)
async def session_time_entered(message: Message, state: FSMContext) -> None:
    raw = normalize_digits(message.text.strip())
    if not is_valid_time_hhmm(raw):
        await message.answer("❌ فرمت ساعت درست نیست. مثال درست: 18:30")
        return

    data = await state.get_data()
    already_entered = data.get("session_times", [])

    if raw in already_entered or sessions_repo.slot_exists(data["new_session_event_id"], data["new_session_date"], raw):
        await message.answer(
            f"⚠️ سانس ساعت {raw} برای این روز از قبل ثبت شده (تکراری است). "
            "لطفاً ساعت دیگری وارد کنید."
        )
        return

    already_entered.append(raw)
    index = len(already_entered)
    total = data["session_total"]
    await state.update_data(session_times=already_entered)

    if index < total:
        await message.answer(_ask_time_prompt(index + 1, total))
        return

    # All times collected — save them all now.
    event_id = data["new_session_event_id"]
    date_str = data["new_session_date"]
    capacity = data["session_capacity"]
    created = []
    for t in already_entered:
        try:
            sid = sessions_repo.create_session(event_id, date_str, t, capacity)
            created.append((sid, t))
        except Exception:
            continue  # duplicate-safety net at the DB layer; already checked above

    logs_repo.record("sessions_created", message.from_user.id,
                      f"event_id={event_id} date={date_str} times={already_entered}")
    await state.clear()

    if created:
        from services import channel_service
        await channel_service.on_reservation_changed(message.bot, created[0][0])

    lines = [f"✅ {len(created)} سانس برای {gregorian_iso_to_jalali_display(date_str)} اضافه شد:"]
    lines += [f"🕒 {t} — ظرفیت {capacity}" for _, t in created]
    await message.answer("\n".join(lines))
    await _render_event_detail(message, event_id)


# ---------------- per-session view / edit / toggle / delete ----------------

@router.callback_query(F.data.startswith("admin_session_view:"))
async def session_view(callback: CallbackQuery) -> None:
    session_id = int(callback.data.split(":")[1])
    session = sessions_repo.get_session(session_id)
    if not session:
        await callback.answer(fa.UNKNOWN_ERROR, show_alert=True)
        return

    reserved = sessions_repo.reserved_count(session_id)
    holders = reservations_repo.list_holders_for_session(session_id)

    lines = [
        f"🕒 {gregorian_iso_to_jalali_display(session['session_date'])} — {session['session_time']}",
        f"وضعیت: {'🟢 فعال' if session['status'] == 'active' else '🟠 غیرفعال'}",
        f"ظرفیت: {reserved}/{session['capacity']} پر شده",
        "",
    ]
    if holders:
        lines.append("👥 افراد دارای رزرو در این سانس:")
        for h in holders:
            code = h["reservation_code"] or "(در انتظار)"
            if h.get("attendee_name"):
                lines.append(
                    f"- خریدار: {h['full_name']} ({h['phone']}) — حاضر: {h['attendee_name']} "
                    f"({h.get('attendee_phone', '—')}) — {h['people']} نفر — {code}"
                )
            else:
                lines.append(f"- {h['full_name']} — {h['people']} نفر — {h['phone']} — {code}")
    else:
        lines.append("هیچ رزروی برای این سانس ثبت نشده.")

    await callback.message.answer(
        "\n".join(lines),
        reply_markup=session_detail_keyboard(session_id, session["event_id"], session["status"] == "active"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_session_manage_res:"))
async def manage_session_reservations(callback: CallbackQuery) -> None:
    from keyboards.admin import holder_edit_keyboard
    session_id = int(callback.data.split(":")[1])
    holders = reservations_repo.list_holders_for_session(session_id)
    if not holders:
        await callback.answer("هیچ رزروی برای ویرایش وجود ندارد.", show_alert=True)
        return
    await callback.message.answer(
        "کدام رزرو را می‌خواهید ویرایش کنید؟",
        reply_markup=holder_edit_keyboard(holders, session_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_res_edit:"))
async def reservation_edit_menu(callback: CallbackQuery) -> None:
    from keyboards.admin import reservation_edit_menu_keyboard
    reservation_id = int(callback.data.split(":")[1])
    await callback.message.answer("چه تغییری می‌خواهید بدهید؟", reply_markup=reservation_edit_menu_keyboard(reservation_id))
    await callback.answer()


@router.callback_query(F.data.startswith("res_edit_people:"))
async def res_edit_people_start(callback: CallbackQuery, state: FSMContext) -> None:
    reservation_id = int(callback.data.split(":")[1])
    await state.update_data(edit_res_id=reservation_id)
    await state.set_state(AdminEventStates.awaiting_reservation_people_edit)
    await callback.message.answer("تعداد نفرات جدید را وارد کنید:")
    await callback.answer()


@router.message(AdminEventStates.awaiting_reservation_people_edit)
async def res_edit_people_save(message: Message, state: FSMContext) -> None:
    from services import reservation_service
    if not is_positive_int(message.text):
        await message.answer(fa.INVALID_NUMBER)
        return

    data = await state.get_data()
    result = reservation_service.admin_update_people(data["edit_res_id"], int(message.text.strip()))
    await state.clear()
    if result["success"]:
        logs_repo.record("reservation_people_edited_by_admin", message.from_user.id, f"reservation_id={data['edit_res_id']}")
        from services import channel_service
        reservation = reservations_repo.get_reservation(data["edit_res_id"])
        await channel_service.on_reservation_changed(message.bot, reservation["session_id"])
        await message.answer(f"✅ تعداد به‌روزرسانی شد. مبلغ جدید: {result['total_price']:,} تومان")
    else:
        await message.answer(f"❌ ظرفیت کافی نیست — حداکثر {result['remaining']} نفر برای این سانس ممکن است.")


@router.callback_query(F.data.startswith("res_edit_move:"))
async def res_edit_move_start(callback: CallbackQuery, state: FSMContext) -> None:
    reservation_id = int(callback.data.split(":")[1])
    reservation = reservations_repo.get_reservation(reservation_id)
    session = sessions_repo.get_session(reservation["session_id"])
    other_sessions = [
        s for s in sessions_repo.list_sessions_for_event_admin(session["event_id"])
        if s["id"] != session["id"] and s["status"] == "active"
    ]
    if not other_sessions:
        await callback.answer("سانس دیگری برای این رویداد وجود ندارد.", show_alert=True)
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = [
        [InlineKeyboardButton(
            text=f"{gregorian_iso_to_jalali_display(s['session_date'])} — {s['session_time']}",
            callback_data=f"res_move_target:{s['id']}",
        )]
        for s in other_sessions
    ]
    await state.update_data(edit_res_id=reservation_id)
    await state.set_state(AdminEventStates.picking_reservation_move_target)
    await callback.message.answer("سانس مقصد را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(AdminEventStates.picking_reservation_move_target, F.data.startswith("res_move_target:"))
async def res_edit_move_do(callback: CallbackQuery, state: FSMContext) -> None:
    from services import reservation_service
    new_session_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    old_reservation = reservations_repo.get_reservation(data["edit_res_id"])
    old_session_id = old_reservation["session_id"] if old_reservation else None
    result = reservation_service.admin_move_reservation(data["edit_res_id"], new_session_id)
    await state.clear()
    if result["success"]:
        logs_repo.record("reservation_moved_by_admin", callback.from_user.id,
                          f"reservation_id={data['edit_res_id']} -> session_id={new_session_id}")
        from services import channel_service
        if old_session_id:
            await channel_service.on_reservation_changed(callback.bot, old_session_id)
        await channel_service.on_reservation_changed(callback.bot, new_session_id)
        await callback.message.answer("✅ رزرو به سانس جدید جابجا شد.")
    else:
        await callback.message.answer(f"❌ ظرفیت کافی در سانس مقصد نیست (باقی‌مانده: {result.get('remaining', 0)}).")
    await callback.answer()


@router.callback_query(F.data.startswith("res_edit_cancel_confirm:"))
async def res_edit_cancel_confirm(callback: CallbackQuery) -> None:
    reservation_id = int(callback.data.split(":")[1])
    await callback.message.answer(
        "آیا مطمئنید می‌خواهید این رزرو را لغو کنید؟ (ظرفیت آزاد خواهد شد)",
        reply_markup=confirm_keyboard(f"res_edit_cancel_do:{reservation_id}", "noop"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("res_edit_cancel_do:"))
async def res_edit_cancel_do(callback: CallbackQuery) -> None:
    from services import reservation_service
    reservation_id = int(callback.data.split(":")[1])
    reservation = reservations_repo.get_reservation(reservation_id)
    reservation_service.admin_cancel_reservation(reservation_id)
    logs_repo.record("reservation_cancelled_by_admin", callback.from_user.id, f"reservation_id={reservation_id}")
    if reservation:
        from services import channel_service
        await channel_service.on_reservation_changed(callback.bot, reservation["session_id"])
    await callback.message.answer("✅ رزرو لغو شد و ظرفیت آزاد گردید.")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_session_toggle:"))
async def session_toggle(callback: CallbackQuery) -> None:
    session_id = int(callback.data.split(":")[1])
    session = sessions_repo.get_session(session_id)
    new_status = "inactive" if session["status"] == "active" else "active"
    sessions_repo.set_session_status(session_id, new_status)
    logs_repo.record("session_toggled", callback.from_user.id, f"session_id={session_id} -> {new_status}")
    await callback.answer("✅ انجام شد.")
    await session_view(callback)


@router.callback_query(F.data.startswith("admin_session_delete_confirm:"))
async def session_delete_confirm(callback: CallbackQuery) -> None:
    session_id = int(callback.data.split(":")[1])
    session = sessions_repo.get_session(session_id)
    reserved = sessions_repo.reserved_count(session_id)
    warning = ""
    if reserved:
        warning = f"\n\n⚠️ توجه: {reserved} نفر برای این سانس رزرو دارند — با حذف سانس، رزروهای آن‌ها هم حذف می‌شود!"
    await callback.message.answer(
        f"آیا مطمئنید می‌خواهید سانس {gregorian_iso_to_jalali_display(session['session_date'])} "
        f"— {session['session_time']} را حذف کنید؟{warning}",
        reply_markup=confirm_keyboard(
            yes_callback=f"admin_session_delete_do:{session_id}",
            no_callback=f"admin_session_view:{session_id}",
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_session_delete_do:"))
async def session_delete_do(callback: CallbackQuery) -> None:
    session_id = int(callback.data.split(":")[1])
    session = sessions_repo.get_session(session_id)
    sessions_repo.delete_session(session_id)
    logs_repo.record("session_deleted", callback.from_user.id, f"session_id={session_id}")
    await callback.message.answer("🗑 سانس حذف شد.")
    if session:
        await _render_event_detail(callback.message, session["event_id"])
    await callback.answer()


@router.callback_query(F.data.startswith("admin_session_edit_capacity:"))
async def edit_capacity_start(callback: CallbackQuery, state: FSMContext) -> None:
    session_id = int(callback.data.split(":")[1])
    await state.update_data(edit_session_id=session_id)
    await state.set_state(AdminEventStates.awaiting_edit_capacity)
    await callback.message.answer("ظرفیت جدید را وارد کنید (عدد):")
    await callback.answer()


@router.message(AdminEventStates.awaiting_edit_capacity)
async def edit_capacity_save(message: Message, state: FSMContext) -> None:
    if not is_positive_int(message.text):
        await message.answer(fa.INVALID_NUMBER)
        return
    data = await state.get_data()
    sessions_repo.update_session(data["edit_session_id"], capacity=int(message.text.strip()))
    logs_repo.record("session_capacity_updated", message.from_user.id, f"session_id={data['edit_session_id']}")
    from services import channel_service
    await channel_service.on_reservation_changed(message.bot, data["edit_session_id"])
    await state.clear()
    await message.answer("✅ ظرفیت به‌روزرسانی شد.")


@router.callback_query(F.data.startswith("admin_session_edit_datetime:"))
async def edit_datetime_start(callback: CallbackQuery, state: FSMContext) -> None:
    from keyboards.admin import any_calendar_keyboard
    from datetime import date as _date
    session_id = int(callback.data.split(":")[1])
    session = sessions_repo.get_session(session_id)
    event = events_repo.get_event(session["event_id"]) if session else None
    calendar_type = (event.get("calendar_type") if event else "jalali") or "jalali"

    if calendar_type == "gregorian":
        today = _date.today()
        year, month = today.year, today.month
        prompt = "Pick the new date:"
    else:
        year, month, _ = today_jalali()
        prompt = "تاریخ جدید را از تقویم انتخاب کنید:"

    await state.update_data(edit_session_id=session_id, edit_calendar_type=calendar_type)
    await state.set_state(AdminEventStates.awaiting_edit_date)
    await callback.message.edit_text(
        prompt, reply_markup=any_calendar_keyboard(year, month, "sess_edit_cal", calendar_type),
    )
    await callback.answer()


@router.callback_query(AdminEventStates.awaiting_edit_date, F.data.startswith("sess_edit_cal:nav:"))
async def edit_calendar_nav(callback: CallbackQuery, state: FSMContext) -> None:
    from keyboards.admin import any_calendar_keyboard
    data = await state.get_data()
    calendar_type = data.get("edit_calendar_type", "jalali")
    _, _, y, m = callback.data.split(":")
    await callback.message.edit_reply_markup(
        reply_markup=any_calendar_keyboard(int(y), int(m), "sess_edit_cal", calendar_type)
    )
    await callback.answer()


@router.callback_query(AdminEventStates.awaiting_edit_date, F.data == "sess_edit_cal:back")
async def edit_calendar_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()


@router.callback_query(AdminEventStates.awaiting_edit_date, F.data.startswith("sess_edit_cal:pick:"))
async def edit_calendar_pick(callback: CallbackQuery, state: FSMContext) -> None:
    iso_date = callback.data.split(":", 2)[2]
    await state.update_data(edit_new_date=iso_date)
    await state.set_state(AdminEventStates.awaiting_edit_time)
    await callback.message.edit_text("ساعت جدید را وارد کنید (مثال: 18:30):")
    await callback.answer()


@router.message(AdminEventStates.awaiting_edit_time)
async def edit_time_save(message: Message, state: FSMContext) -> None:
    raw = normalize_digits(message.text.strip())
    if not is_valid_time_hhmm(raw):
        await message.answer("❌ فرمت ساعت درست نیست. مثال درست: 18:30")
        return

    data = await state.get_data()
    session = sessions_repo.get_session(data["edit_session_id"])
    if sessions_repo.slot_exists(session["event_id"], data["edit_new_date"], raw):
        await message.answer("⚠️ سانسی با همین تاریخ و ساعت از قبل وجود دارد. ساعت دیگری وارد کنید.")
        return

    sessions_repo.update_session(data["edit_session_id"], session_date=data["edit_new_date"], session_time=raw)
    logs_repo.record("session_datetime_updated", message.from_user.id, f"session_id={data['edit_session_id']}")
    await state.clear()
    await message.answer("✅ تاریخ/ساعت سانس به‌روزرسانی شد.")
