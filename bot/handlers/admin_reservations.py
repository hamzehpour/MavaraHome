from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from texts import fa
from filters.admin_filter import IsAdmin
from states.admin_states import AdminReviewStates
from services import reservation_service, settings_service
from database.repositories import reservations as reservations_repo
from database.repositories import sessions as sessions_repo
from database.repositories import events as events_repo
from database.repositories import logs as logs_repo
from utils.logger import get_logger

router = Router(name="admin_reservations")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

logger = get_logger()


@router.callback_query(F.data == "admin:pending")
async def list_pending(callback: CallbackQuery) -> None:
    pending = reservations_repo.list_pending_review()
    if not pending:
        await callback.message.answer(fa.NO_PENDING_RESERVATIONS)
        await callback.answer()
        return

    for res in pending:
        from keyboards.admin import reservation_review_keyboard
        await callback.message.answer(
            fa.admin_reservation_card(res),
            reply_markup=reservation_review_keyboard(res["id"]),
        )
    await callback.answer()


async def _safe_ack_admin_message(callback: CallbackQuery, extra_line: str) -> None:
    """
    The message being acted on might be a photo (caption) or a plain text
    message, depending on where the admin tapped Approve/Reject from — this
    handles both instead of crashing with an unhandled exception when
    edit_caption() is called on a text-only message (the bug that could
    silently break the flow right after the buyer was already notified).
    """
    try:
        if callback.message.caption is not None:
            await callback.message.edit_caption(caption=(callback.message.caption or "") + f"\n\n{extra_line}")
        else:
            await callback.message.edit_text((callback.message.text or "") + f"\n\n{extra_line}")
    except Exception:
        try:
            await callback.message.answer(extra_line)
        except Exception:
            pass


async def _notify_buyer(bot: Bot, telegram_id: int | None, **send_kwargs) -> bool:
    if not telegram_id:
        return False

    if "photo" in send_kwargs:
        # Telegram photo captions are capped at 1024 characters — a
        # real-world ticket (address + arrival instructions + support
        # numbers) routinely exceeds that, which made send_photo raise
        # MESSAGE_CAPTION_TOO_LONG and get misreported as "buyer probably
        # blocked the bot". Sending the text as its own message (4096-char
        # limit) first, then the QR with no caption, makes delivery robust
        # regardless of template length — and the two sends are tracked
        # independently so a QR failure never erases an already-delivered
        # text (the text carries the critical info: address, code, instructions).
        caption = send_kwargs.pop("caption", None)
        parse_mode = send_kwargs.pop("parse_mode", None)
        text_delivered = False
        if caption:
            text_delivered = await _send_text_with_fallback(bot, telegram_id, caption, parse_mode)
        try:
            await bot.send_photo(telegram_id, **send_kwargs)
        except Exception:
            logger.exception("Failed to send QR photo to buyer telegram_id=%s", telegram_id)
        return text_delivered

    text = send_kwargs.pop("text", None)
    parse_mode = send_kwargs.pop("parse_mode", None)
    if text is not None:
        return await _send_text_with_fallback(bot, telegram_id, text, parse_mode, **send_kwargs)

    try:
        await bot.send_message(telegram_id, **send_kwargs)
        return True
    except Exception:
        logger.exception("Failed to notify buyer telegram_id=%s", telegram_id)
        return False


async def _send_text_with_fallback(bot: Bot, telegram_id: int, text: str, parse_mode: str | None,
                                    **extra_kwargs) -> bool:
    """
    Sends the text and, if it fails specifically because of a Markdown
    parsing error (a single stray '_' or '*' in a buyer/attendee name or
    an admin-edited template is enough to break legacy Markdown parsing),
    retries once with parse_mode stripped — plain text always delivers.
    A real block/deactivated-account failure is NOT retried (nothing would
    help) and is reported accurately instead of being lumped in with
    formatting issues under the same generic 'probably blocked' message.
    extra_kwargs (e.g. reply_markup) are forwarded to both the primary
    attempt and the plain-text fallback so buttons never silently vanish.
    """
    try:
        await bot.send_message(telegram_id, text, parse_mode=parse_mode, **extra_kwargs)
        return True
    except Exception as exc:
        error_text = str(exc).lower()
        is_parse_error = "can't parse" in error_text or "can't find end" in error_text or "entities" in error_text
        if parse_mode and is_parse_error:
            try:
                await bot.send_message(telegram_id, text, **extra_kwargs)  # no parse_mode — always delivers
                logger.warning(
                    "Ticket text to telegram_id=%s had a Markdown parse error, delivered as plain text instead",
                    telegram_id,
                )
                return True
            except Exception:
                logger.exception("Plain-text fallback also failed for telegram_id=%s", telegram_id)
                return False
        logger.exception("Failed to send text to buyer telegram_id=%s", telegram_id)
        return False


@router.callback_query(F.data.startswith("review:approve:"))
async def approve(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    reservation_id = int(callback.data.split(":")[2])
    await callback.answer()

    from database.connection import get_connection
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT r.*, u.telegram_id AS user_telegram_id, u.full_name AS user_full_name
            FROM reservations r JOIN users u ON u.id = r.user_id
            WHERE r.id = ?
            """,
            (reservation_id,),
        ).fetchone()
    reservation = dict(row) if row else None
    if not reservation:
        await callback.message.answer(fa.UNKNOWN_ERROR)
        return

    # Fast-path UX check (not the real guarantee — see below) so a normal
    # double-tap shows a friendly message immediately instead of just
    # silently no-op'ing.
    if reservation["status"] != "pending_review":
        await callback.answer("این رزرو قبلاً پردازش شده — دوباره پردازش نشد.", show_alert=True)
        return

    result = reservation_service.approve_reservation(reservation_id, callback.from_user.id)
    if result is None:
        # The real (atomic) guard caught a race the fast-path check above
        # could theoretically miss — e.g. another admin's tap landed in the
        # same instant. Either way, nothing was double-processed.
        await callback.answer("این رزرو هم‌زمان توسط شخص دیگری پردازش شد.", show_alert=True)
        return
    code, qr_bytes = result
    from aiogram.types import BufferedInputFile
    qr_image = BufferedInputFile(qr_bytes, filename="ticket.png")
    logs_repo.record("reservation_approved", callback.from_user.id, f"reservation_id={reservation_id}",
                      target_type="reservation", target_id=reservation_id)

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

    delivered = await _notify_buyer(
        bot, reservation.get("user_telegram_id"),
        photo=qr_image, caption=ticket_text, parse_mode="Markdown",
    )

    if delivered:
        await _safe_ack_admin_message(callback, fa.RESERVATION_APPROVED_ADMIN_SIDE)
    else:
        await _safe_ack_admin_message(
            callback,
            f"⚠️ رزرو تأیید شد ولی ارسال پیام به خریدار ناموفق بود "
            f"(آیدی تلگرام: {reservation.get('user_telegram_id')}). "
            f"احتمالاً کاربر ربات را بلاک کرده — لطفاً تلفنی پیگیری کنید.",
        )

    # Give the admin the option to add a short note for the buyer — e.g.
    # "برای یک نفر رزرو ثبت شد، مابقی هزینه را جداگانه واریز کنید".
    if delivered:
        await state.update_data(approve_note_target=reservation.get("user_telegram_id"))
        await state.set_state(AdminReviewStates.awaiting_approve_note)
        await callback.message.answer(
            "می‌خواهید یادداشت کوتاهی هم برای خریدار ارسال کنید؟ (اختیاری)\n"
            "اگر بله، همین الان بنویسید. اگر نه، «-» ارسال کنید.",
        )


@router.message(AdminReviewStates.awaiting_approve_note)
async def finish_approve_note(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    target = data.get("approve_note_target")
    await state.clear()

    note = message.text.strip()
    if note == "-" or not note:
        return

    delivered = await _notify_buyer(bot, target, text=f"📝 یادداشت از تیم مجموعه:\n\n{note}")
    if delivered:
        await message.answer("✅ یادداشت برای خریدار ارسال شد.")
    else:
        await message.answer("⚠️ ارسال یادداشت به خریدار ناموفق بود.")


@router.callback_query(F.data.startswith("review:reject:"))
async def start_reject(callback: CallbackQuery, state: FSMContext) -> None:
    from keyboards.admin import reject_reason_menu_keyboard
    reservation_id = int(callback.data.split(":")[2])
    await state.update_data(reject_reservation_id=reservation_id)
    await callback.message.answer(fa.ADMIN_REJECT_REASON_MENU, reply_markup=reject_reason_menu_keyboard(reservation_id))
    await callback.answer()


@router.callback_query(F.data.startswith("reject_reason_mode:"))
async def reject_reason_mode(callback: CallbackQuery, state: FSMContext) -> None:
    _, mode, reservation_id_str = callback.data.split(":")
    reservation_id = int(reservation_id_str)

    if mode == "type":
        await state.set_state(AdminReviewStates.awaiting_reject_reason)
        await callback.message.answer(fa.ASK_REJECT_REASON)
        await callback.answer()
        return

    # mode == "receipt" — skip typing, use the preset reason directly.
    await _apply_rejection(callback.message, callback.from_user.id, reservation_id,
                            fa.RECEIPT_PROBLEM_PRESET_REASON, callback.bot)
    await callback.answer()


async def _apply_rejection(target, admin_telegram_id: int, reservation_id: int, reason: str, bot: Bot) -> None:
    transitioned = reservation_service.mark_awaiting_buyer_confirmation(reservation_id, reason)
    if not transitioned:
        await target.answer("این رزرو قبلاً پردازش شده — دوباره پردازش نشد.")
        return

    logs_repo.record("reservation_reject_pending_confirmation", admin_telegram_id,
                      f"reservation_id={reservation_id}: {reason}",
                      target_type="reservation", target_id=reservation_id)

    from database.connection import get_connection
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT u.telegram_id FROM reservations r
            JOIN users u ON u.id = r.user_id WHERE r.id = ?
            """,
            (reservation_id,),
        ).fetchone()

    from keyboards.admin import reject_confirm_keyboard
    delivered = await _notify_buyer(
        bot, row["telegram_id"] if row else None,
        text=fa.reject_notice_to_buyer(reason),
        reply_markup=reject_confirm_keyboard(reservation_id),
    )
    if delivered:
        await target.answer(
            "رد پرداخت برای خریدار ارسال شد و منتظر پاسخ او هستیم — "
            "تا تعیین‌تکلیف نهایی، صندلی این رزرو همچنان رزرو شده باقی می‌ماند."
        )
    else:
        await target.answer(
            f"⚠️ رزرو رد شد ولی ارسال پیام به خریدار ناموفق بود "
            f"(آیدی تلگرام: {row['telegram_id'] if row else '-'})."
        )


@router.message(AdminReviewStates.awaiting_reject_reason)
async def finish_reject(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    reservation_id = data["reject_reservation_id"]
    reason = "" if message.text.strip() == "-" else message.text.strip()
    await state.clear()
    await _apply_rejection(message, message.from_user.id, reservation_id, reason, bot)
