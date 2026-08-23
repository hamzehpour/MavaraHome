"""
The grace period after an admin taps Reject: the seat stays held (see
services/reservation_service.mark_awaiting_buyer_confirmation) until this
flow resolves one way or the other — either the buyer accepts the
cancellation, or disputes it and an admin makes the final call.
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from texts import fa
from states.dispute_states import DisputeStates, DisputeAgainStates
from states.resend_receipt_states import ResendReceiptStates
from services import reservation_service
from database.repositories import admins as admins_repo
from database.repositories import reservations as reservations_repo
from database.repositories import logs as logs_repo
from utils.safe_send import safe_send_message
from database.connection import get_connection

router = Router(name="reject_confirmation")


def _get_reservation_with_user(reservation_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT r.*, u.telegram_id AS user_telegram_id, u.full_name AS user_full_name,
                   u.phone AS user_phone
            FROM reservations r JOIN users u ON u.id = r.user_id
            WHERE r.id = ?
            """,
            (reservation_id,),
        ).fetchone()
        return dict(row) if row else None


@router.callback_query(F.data.startswith("reject_confirm:accept:"))
async def buyer_accepts_cancellation(callback: CallbackQuery) -> None:
    reservation_id = int(callback.data.split(":")[2])
    reservation = _get_reservation_with_user(reservation_id)
    if not reservation:
        await callback.answer()
        return

    transitioned = reservation_service.finalize_rejection_if(
        reservation_id, "awaiting_buyer_confirmation", reviewed_by=0,
        reason=reservation.get("admin_note") or "",
    )
    if not transitioned:
        await callback.answer("این رزرو قبلاً پردازش شده.", show_alert=True)
        return

    logs_repo.record("buyer_accepted_cancellation", callback.from_user.id, f"reservation_id={reservation_id}")
    from services import channel_service
    await channel_service.on_reservation_changed(callback.bot, reservation["session_id"])
    await callback.message.edit_text(fa.RESERVATION_CANCELLED_BY_BUYER)
    await callback.answer()


@router.callback_query(F.data.startswith("reject_confirm:resend:"))
async def buyer_wants_to_resend_receipt(callback: CallbackQuery, state: FSMContext) -> None:
    reservation_id = int(callback.data.split(":")[2])
    reservation = _get_reservation_with_user(reservation_id)
    if not reservation or reservation["status"] != "awaiting_buyer_confirmation":
        await callback.answer("این رزرو دیگر در این وضعیت نیست.", show_alert=True)
        return

    await state.update_data(resend_reservation_id=reservation_id)
    await state.set_state(ResendReceiptStates.awaiting_new_receipt)
    await callback.message.edit_text(fa.ASK_NEW_RECEIPT_PHOTO)
    await callback.answer()


@router.message(ResendReceiptStates.awaiting_new_receipt, F.photo)
async def buyer_resends_receipt(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    reservation_id = data["resend_reservation_id"]
    await state.clear()

    fresh = reservations_repo.get_reservation(reservation_id)
    if not fresh or fresh["status"] != "awaiting_buyer_confirmation":
        await message.answer(fa.UNKNOWN_ERROR)
        return

    file_id = message.photo[-1].file_id
    reservation_service.submit_receipt(reservation_id, file_id)
    logs_repo.record("receipt_resubmitted", message.from_user.id, f"reservation_id={reservation_id}",
                      target_type="reservation", target_id=reservation_id)
    await message.answer(fa.NEW_RECEIPT_SUBMITTED_BUYER_SIDE)

    # Re-notify staff exactly like the first submission did.
    from keyboards.admin import reservation_review_keyboard
    from services import permissions
    user = _get_reservation_with_user(reservation_id)
    text = fa.admin_reservation_card(user)
    for telegram_id in permissions.list_staff_with_permission(permissions.APPROVE_PAYMENTS):
        try:
            await bot.send_photo(telegram_id, photo=file_id, caption=text,
                                  reply_markup=reservation_review_keyboard(reservation_id))
        except Exception:
            continue


@router.message(ResendReceiptStates.awaiting_new_receipt)
async def buyer_resend_wrong_type(message: Message) -> None:
    await message.answer(fa.RECEIPT_MUST_BE_PHOTO)


@router.callback_query(F.data.startswith("reject_confirm:dispute:"))
async def buyer_disputes(callback: CallbackQuery, state: FSMContext) -> None:
    reservation_id = int(callback.data.split(":")[2])
    await state.update_data(dispute_reservation_id=reservation_id)
    await state.set_state(DisputeStates.awaiting_buyer_explanation)
    await callback.message.edit_text(fa.ASK_DISPUTE_EXPLANATION)
    await callback.answer()


@router.message(DisputeStates.awaiting_buyer_explanation)
async def forward_dispute_to_admins(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    reservation_id = data["dispute_reservation_id"]
    await state.clear()

    reservation = _get_reservation_with_user(reservation_id)
    if not reservation:
        await message.answer(fa.UNKNOWN_ERROR)
        return

    from keyboards.admin import dispute_resolve_keyboard
    from services import permissions
    text = fa.dispute_notify_admin(
        reservation["user_full_name"], reservation["user_phone"],
        reservation.get("admin_note") or "", message.text or "",
    )
    for telegram_id in permissions.list_staff_with_permission(permissions.APPROVE_PAYMENTS):
        try:
            await bot.send_message(telegram_id, text, reply_markup=dispute_resolve_keyboard(reservation_id))
        except Exception:
            continue

    logs_repo.record("buyer_disputed_rejection", message.from_user.id, f"reservation_id={reservation_id}")
    await message.answer(fa.DISPUTE_SENT_TO_BUYER_SIDE)


@router.callback_query(F.data.startswith("dispute_resolve:"))
async def resolve_dispute(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    from services import permissions
    if not permissions.staff_has_permission(callback.from_user.id, permissions.APPROVE_PAYMENTS):
        await callback.answer()
        return

    _, decision, reservation_id_str = callback.data.split(":")
    reservation_id = int(reservation_id_str)
    reservation = _get_reservation_with_user(reservation_id)
    if not reservation:
        await callback.answer(fa.UNKNOWN_ERROR, show_alert=True)
        return

    if decision == "approve":
        from services import settings_service
        from database.repositories import sessions as sessions_repo
        from database.repositories import events as events_repo

        # This is the dispute-resolution path: the reservation is currently
        # in awaiting_buyer_confirmation (buyer disputed an earlier reject),
        # not pending_review — so the expected starting status must match.
        result = reservation_service.approve_reservation(
            reservation_id, callback.from_user.id, expected_status="awaiting_buyer_confirmation"
        )
        if result is None:
            await callback.answer("این رزرو قبلاً پردازش شده بود.", show_alert=True)
            return
        code, qr_bytes = result
        session = sessions_repo.get_session(reservation["session_id"])
        event = events_repo.get_event(session["event_id"]) if session else None
        ticket_text = settings_service.render_ticket_confirmed(
            event_title=event["title"] if event else "",
            session_date_iso=session["session_date"] if session else "",
            session_time=session["session_time"] if session else "",
            people=reservation["people"],
            full_name=reservation.get("attendee_name") or reservation["user_full_name"],
            reservation_code=code,
            total_price=reservation["total_price"],
            event_address=(event.get("address") if event else "") or "",
        calendar_type=(event.get("calendar_type") if event else "jalali") or "jalali",
        )
        try:
            await safe_send_message(bot, reservation["user_telegram_id"], ticket_text, parse_mode="Markdown")
        except Exception:
            pass
        try:
            from aiogram.types import BufferedInputFile
            await bot.send_photo(reservation["user_telegram_id"], photo=BufferedInputFile(qr_bytes, filename="ticket.png"))
        except Exception:
            pass
        logs_repo.record("dispute_resolved_approved", callback.from_user.id, f"reservation_id={reservation_id}")
        from services import channel_service
        await channel_service.on_reservation_changed(bot, reservation["session_id"])
        await callback.message.answer("✅ رزرو تأیید و بلیت صادر شد.")
        await callback.answer()
        return

    if decision == "reject":
        from keyboards.admin import confirm_keyboard
        await callback.message.answer(
            fa.DISPUTE_FINAL_REJECT_CONFIRM,
            reply_markup=confirm_keyboard(f"dispute_final_reject:{reservation_id}", "noop"),
        )
        await callback.answer()
        return

    if decision == "again":
        await state.update_data(dispute_again_reservation_id=reservation_id)
        await state.set_state(DisputeAgainStates.awaiting_new_reason)
        await callback.message.answer(fa.ASK_REJECT_AGAIN_REASON)
        await callback.answer()
        return

    await callback.answer()


@router.callback_query(F.data.startswith("dispute_final_reject:"))
async def dispute_final_reject_confirmed(callback: CallbackQuery, bot: Bot) -> None:
    from services import permissions
    if not permissions.staff_has_permission(callback.from_user.id, permissions.APPROVE_PAYMENTS):
        await callback.answer()
        return

    reservation_id = int(callback.data.split(":")[1])
    reservation = _get_reservation_with_user(reservation_id)
    if not reservation:
        await callback.answer(fa.UNKNOWN_ERROR, show_alert=True)
        return

    transitioned = reservation_service.finalize_rejection_if(
        reservation_id, "awaiting_buyer_confirmation", callback.from_user.id,
        reservation.get("admin_note") or "",
    )
    if not transitioned:
        await callback.answer("این رزرو قبلاً پردازش شده بود.", show_alert=True)
        return
    try:
        await bot.send_message(reservation["user_telegram_id"], fa.RESERVATION_FINAL_REJECTED)
    except Exception:
        pass
    logs_repo.record("dispute_resolved_rejected", callback.from_user.id, f"reservation_id={reservation_id}")
    from services import channel_service
    await channel_service.on_reservation_changed(bot, reservation["session_id"])
    await callback.message.answer(fa.DISPUTE_RESOLVED_REJECTED_ADMIN_SIDE)
    await callback.answer()


@router.message(DisputeAgainStates.awaiting_new_reason)
async def dispute_again_new_reason(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    reservation_id = data["dispute_again_reservation_id"]
    reason = message.text.strip()
    await state.clear()

    reservation = _get_reservation_with_user(reservation_id)
    if not reservation or reservation["status"] != "awaiting_buyer_confirmation":
        await message.answer(fa.UNKNOWN_ERROR)
        return

    from database.repositories import reservations as reservations_repo_
    reservations_repo_.set_status(reservation_id, "awaiting_buyer_confirmation", admin_note=reason)
    logs_repo.record("reservation_rejected_again", message.from_user.id,
                      f"reservation_id={reservation_id}: {reason}",
                      target_type="reservation", target_id=reservation_id)

    from keyboards.admin import reject_confirm_keyboard
    try:
        await bot.send_message(
            reservation["user_telegram_id"], fa.reject_notice_to_buyer(reason),
            reply_markup=reject_confirm_keyboard(reservation_id),
        )
        await message.answer("✅ دلیل جدید برای خریدار ارسال شد.")
    except Exception:
        await message.answer("⚠️ ارسال پیام به خریدار ناموفق بود.")
