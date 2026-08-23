"""
Resolves an overflow-capacity request from the waitlist: an admin can grow
the session's capacity to fit the waiting person and automatically push
them into the payment step, or decline.
"""
from aiogram import Router, F, Bot, Dispatcher
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

from texts import fa
from filters.admin_filter import HasPermission
from services import permissions as perm
from database.repositories import waitlist as waitlist_repo
from database.repositories import logs as logs_repo
from services import reservation_service, settings_service
from states.booking_states import BookingStates
from utils.safe_send import safe_send_message

router = Router(name="overflow_requests")
router.callback_query.filter(HasPermission(perm.REQUEST_OVERFLOW_DECISION))


@router.callback_query(F.data.startswith("overflow:approve:"))
async def approve_overflow(callback: CallbackQuery, bot: Bot, dispatcher: Dispatcher) -> None:
    waitlist_id = int(callback.data.split(":")[2])
    entry = waitlist_repo.get_entry_with_context(waitlist_id)
    if not entry or entry["status"] != "waiting":
        await callback.answer(fa.UNKNOWN_ERROR, show_alert=True)
        return

    if not waitlist_repo.set_status_if(waitlist_id, "waiting", "converted"):
        await callback.answer("این درخواست قبلاً پردازش شده بود.", show_alert=True)
        return

    new_capacity = entry["capacity"] + entry["people"]
    logs_repo.record("overflow_approved", callback.from_user.id,
                      f"waitlist_id={waitlist_id} new_capacity={new_capacity}")

    result = reservation_service.approve_overflow_atomic(
        session_id=entry["session_id"], user_id=entry["user_id"], people=entry["people"],
    )
    if result.get("success"):
        # Bug fix (reported): approving an overflow request never told the
        # buyer to send a receipt, and even if they sent one anyway it was
        # silently ignored — the buyer's FSM was never in awaiting_receipt
        # (that state is normally reached by the buyer clicking through the
        # regular booking flow; here the "click" was the admin's approval,
        # on someone else's chat). Both are fixed below: send the same
        # instructions the normal flow sends, AND put the buyer's FSM into
        # awaiting_receipt with this reservation_id so their next photo is
        # picked up by the existing receipt handler exactly like a normal
        # booking — same admin-approve/reject path, same ticket issuance.
        await safe_send_message(bot, entry["telegram_id"], fa.OVERFLOW_APPROVED_BUYER_MSG)
        await safe_send_message(
            bot, entry["telegram_id"],
            settings_service.render_payment_instructions(
                people=entry["people"], unit_price=result["unit_price"], total_price=result["total_price"],
            ),
            parse_mode="Markdown",
        )
        await safe_send_message(bot, entry["telegram_id"], fa.ASK_RECEIPT_PHOTO)

        buyer_state = FSMContext(
            storage=dispatcher.storage,
            key=StorageKey(bot_id=bot.id, chat_id=entry["telegram_id"], user_id=entry["telegram_id"]),
        )
        await buyer_state.set_state(BookingStates.awaiting_receipt)
        await buyer_state.update_data(reservation_id=result["reservation_id"])

        from services import channel_service
        await channel_service.on_reservation_changed(bot, entry["session_id"])

    await callback.message.answer(fa.OVERFLOW_RESOLVED_ADMIN_SIDE)
    await callback.answer()


@router.callback_query(F.data.startswith("overflow:reject:"))
async def reject_overflow(callback: CallbackQuery, bot: Bot) -> None:
    waitlist_id = int(callback.data.split(":")[2])
    entry = waitlist_repo.get_entry_with_context(waitlist_id)
    if not entry:
        await callback.answer(fa.UNKNOWN_ERROR, show_alert=True)
        return

    if not waitlist_repo.set_status_if(waitlist_id, "waiting", "rejected"):
        await callback.answer("این درخواست قبلاً پردازش شده.", show_alert=True)
        return

    logs_repo.record("overflow_rejected", callback.from_user.id, f"waitlist_id={waitlist_id}")
    try:
        await bot.send_message(entry["telegram_id"], fa.OVERFLOW_REJECTED_BUYER_MSG)
    except Exception:
        pass
    await callback.message.answer(fa.OVERFLOW_RESOLVED_ADMIN_SIDE)
    await callback.answer()
