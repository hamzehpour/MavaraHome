from aiogram import Router, F, Bot, Dispatcher
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

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


def _admin_dm_state(dispatcher: Dispatcher, bot: Bot, admin_telegram_id: int) -> FSMContext:
    """A callback tapped from the alerts channel/group (see handlers/
    channel_setup.py) carries THAT chat's id, not the admin's own —
    setting FSM state there would try to match the admin's next reply
    against the wrong chat. Worse, if it's a genuine Telegram *channel*
    (not a group), a member's typed reply never even reaches the bot as a
    normal message at all — Telegram delivers it as a channel_post,
    attributed to the channel itself (no from_user), which aiogram's
    @router.message() handlers never see. Every follow-up that needs the
    admin to type free text is collected in their own DM instead,
    regardless of where the button was tapped — identical to today's
    behavior when it's already a DM, and the only way it can work at all
    when the button was in a channel."""
    return FSMContext(
        storage=dispatcher.storage,
        key=StorageKey(bot_id=bot.id, chat_id=admin_telegram_id, user_id=admin_telegram_id),
    )


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
async def approve(callback: CallbackQuery, bot: Bot, dispatcher: Dispatcher) -> None:
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
    # silently no-op'ing. needs_correction is a valid starting point too —
    # an admin who sent a "نیازمند اصلاح" message can still approve
    # directly afterwards (see reservation_service.approve_reservation's
    # docstring) instead of being forced to wait on a resubmission.
    if reservation["status"] not in ("pending_review", "needs_correction"):
        await callback.answer("این رزرو قبلاً پردازش شده — دوباره پردازش نشد.", show_alert=True)
        return

    result = reservation_service.approve_reservation(reservation_id, callback.from_user.id)
    if result is None:
        # The real (atomic) guard caught a race the fast-path check above
        # could theoretically miss — e.g. another admin's tap landed in the
        # same instant. Either way, nothing was double-processed.
        await callback.answer("این رزرو هم‌زمان توسط شخص دیگری پردازش شد.", show_alert=True)
        return
    code, qr_bytes, email_sent = result
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
    elif not reservation.get("user_telegram_id"):
        # A website-only customer has no Telegram account to message at
        # all — this isn't a delivery failure, it's the expected shape
        # for this buyer. The confirmation email was already attempted
        # inside reservation_service.approve_reservation() (see
        # _notify_customer_by_email) before this handler even started —
        # the old message here ("کاربر ربات را بلاک کرده — تلفنی پیگیری
        # کنید") was actively misleading for this case, since there was
        # never a Telegram delivery to fail in the first place.
        #
        # `email_sent` is the REAL outcome, not just "does this buyer
        # have an email on file" — those look identical until the SMTP
        # server actually rejects the send (bad credentials, etc.), which
        # is exactly the bug this replaced: the admin was told the email
        # went out when it silently hadn't.
        if email_sent:
            await _safe_ack_admin_message(callback, "✅ رزرو تأیید شد — چون این خریدار تلگرام ندارد، تأییدیه از طریق ایمیل برایش ارسال شد.")
        else:
            await _safe_ack_admin_message(
                callback,
                "⚠️ رزرو تأیید شد، ولی ارسال ایمیل تأییدیه به این خریدار ناموفق بود "
                "(یا ایمیلی ثبت نکرده، یا سرویس ایمیل خطا داد — لاگ سرور را چک کنید). "
                "لطفاً تلفنی پیگیری کنید.",
            )
    else:
        await _safe_ack_admin_message(
            callback,
            f"⚠️ رزرو تأیید شد ولی ارسال پیام به خریدار ناموفق بود "
            f"(آیدی تلگرام: {reservation.get('user_telegram_id')}). "
            f"احتمالاً کاربر ربات را بلاک کرده — لطفاً تلفنی پیگیری کنید.",
        )

    # Give the admin the option to add a short note for the buyer — e.g.
    # "برای یک نفر رزرو ثبت شد، مابقی هزینه را جداگانه واریز کنید". Prompted
    # (and collected) in the admin's own DM — see _admin_dm_state()'s
    # docstring for why this can't just use the callback's own chat.
    # Best-effort: the ticket itself already went out by this point, so a
    # failed prompt (admin never started a DM with the bot) isn't worth
    # surfacing as an error over.
    if delivered:
        dm_state = _admin_dm_state(dispatcher, bot, callback.from_user.id)
        await dm_state.update_data(approve_note_target=reservation.get("user_telegram_id"))
        await dm_state.set_state(AdminReviewStates.awaiting_approve_note)
        try:
            await bot.send_message(
                callback.from_user.id,
                "می‌خواهید یادداشت کوتاهی هم برای خریدار ارسال کنید؟ (اختیاری)\n"
                "اگر بله، همین الان بنویسید. اگر نه، «-» ارسال کنید.",
            )
        except Exception:
            pass


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


@router.callback_query(F.data.startswith("review:correct:"))
async def start_correction(callback: CallbackQuery, bot: Bot, dispatcher: Dispatcher) -> None:
    reservation_id = int(callback.data.split(":")[2])
    dm_state = _admin_dm_state(dispatcher, bot, callback.from_user.id)
    await dm_state.update_data(correction_reservation_id=reservation_id)
    await dm_state.set_state(AdminReviewStates.awaiting_correction_message)
    try:
        await bot.send_message(callback.from_user.id, fa.ASK_CORRECTION_MESSAGE)
    except Exception:
        # Admin never started a private chat with the bot — the only way
        # this prompt can reach them at all. Reported plainly rather than
        # silently doing nothing (the bug this whole function replaces).
        await callback.answer(fa.ADMIN_MUST_START_BOT_DM, show_alert=True)
        return
    # Nothing visibly changes on the alert message itself (tapped from a
    # channel/group, where editing it is deliberately left alone) — this
    # toast is what tells the admin the tap actually did something and
    # where to look next.
    await callback.answer("توضیح اصلاح را در چت خصوصی ربات بنویسید 👇")


@router.message(AdminReviewStates.awaiting_correction_message)
async def finish_correction(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    reservation_id = data["correction_reservation_id"]
    await state.clear()

    correction_message = message.text.strip()
    if not correction_message:
        await message.answer(fa.ASK_CORRECTION_MESSAGE)
        await state.set_state(AdminReviewStates.awaiting_correction_message)
        await state.update_data(correction_reservation_id=reservation_id)
        return

    ok = reservation_service.request_correction(reservation_id, message.from_user.id, correction_message)
    if not ok:
        await message.answer("این رزرو قبلاً پردازش شده — دوباره پردازش نشد.")
        return

    logs_repo.record("reservation_needs_correction", message.from_user.id,
                      f"reservation_id={reservation_id}: {correction_message}",
                      target_type="reservation", target_id=reservation_id)
    await message.answer(fa.RESERVATION_NEEDS_CORRECTION_ADMIN_SIDE)


@router.callback_query(F.data.startswith("review:reject:"))
async def start_reject(callback: CallbackQuery, state: FSMContext) -> None:
    from keyboards.admin import reject_reason_menu_keyboard
    reservation_id = int(callback.data.split(":")[2])
    await state.update_data(reject_reservation_id=reservation_id)
    await callback.message.answer(fa.ADMIN_REJECT_REASON_MENU, reply_markup=reject_reason_menu_keyboard(reservation_id))
    await callback.answer()


@router.callback_query(F.data.startswith("reject_reason_mode:"))
async def reject_reason_mode(callback: CallbackQuery, bot: Bot, dispatcher: Dispatcher) -> None:
    _, mode, reservation_id_str = callback.data.split(":")
    reservation_id = int(reservation_id_str)

    if mode == "type":
        # Collected in the admin's own DM — see _admin_dm_state()'s
        # docstring (same reasoning as the "نیازمند اصلاح" message above).
        dm_state = _admin_dm_state(dispatcher, bot, callback.from_user.id)
        await dm_state.update_data(reject_reservation_id=reservation_id)
        await dm_state.set_state(AdminReviewStates.awaiting_reject_reason)
        try:
            await bot.send_message(callback.from_user.id, fa.ASK_REJECT_REASON)
        except Exception:
            await callback.answer(fa.ADMIN_MUST_START_BOT_DM, show_alert=True)
            return
        await callback.answer("دلیل رد را در چت خصوصی ربات بنویسید 👇")
        return

    # mode == "receipt" — skip typing, use the preset reason directly.
    await _apply_rejection(callback.message, callback.from_user.id, reservation_id,
                            fa.RECEIPT_PROBLEM_PRESET_REASON, callback.bot)
    await callback.answer()


async def _apply_rejection(target, admin_telegram_id: int, reservation_id: int, reason: str, bot: Bot) -> None:
    """Reject is direct and final now — same logic as the website admin
    panel's own reject action, no more Telegram-only grace period (see
    reservation_service.reject_reservation()'s docstring for why that was
    removed: "نیازمند اصلاح" already covers "something's fixable, don't
    reject outright", and the grace period never even reached a website-
    only buyer in the first place). Notifies the buyer on every channel
    available — a plain Telegram DM (no buttons; there's nothing left for
    them to decide) if they have one, and always by email."""
    email_sent = reservation_service.reject_reservation(reservation_id, admin_telegram_id, reason)
    if email_sent is None:
        await target.answer("این رزرو قبلاً پردازش شده — دوباره پردازش نشد.")
        return

    logs_repo.record("reservation_rejected", admin_telegram_id, f"reservation_id={reservation_id}: {reason}",
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
    buyer_telegram_id = row["telegram_id"] if row else None

    telegram_delivered = await _notify_buyer(bot, buyer_telegram_id, text=fa.rejection_notice_to_buyer(reason))

    if telegram_delivered and email_sent:
        await target.answer("✅ رزرو رد شد — به خریدار هم از طریق تلگرام و هم ایمیل اطلاع داده شد.")
    elif telegram_delivered:
        await target.answer("✅ رزرو رد شد و از طریق تلگرام به خریدار اطلاع داده شد (ارسال ایمیل ناموفق بود یا ایمیلی ثبت نشده).")
    elif email_sent:
        await target.answer("✅ رزرو رد شد — چون ارسال تلگرام ناموفق بود (یا این خریدار تلگرام ندارد)، اطلاع‌رسانی از طریق ایمیل انجام شد.")
    else:
        await target.answer(
            "⚠️ رزرو رد شد، ولی نه پیام تلگرام و نه ایمیل به خریدار نرسید "
            "(احتمالاً ربات را بلاک کرده و ایمیلی هم ثبت نکرده، یا سرویس ایمیل خطا داد — لاگ سرور را چک کنید). "
            "لطفاً تلفنی پیگیری کنید."
        )


@router.message(AdminReviewStates.awaiting_reject_reason)
async def finish_reject(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    reservation_id = data["reject_reservation_id"]
    reason = "" if message.text.strip() == "-" else message.text.strip()
    await state.clear()
    await _apply_rejection(message, message.from_user.id, reservation_id, reason, bot)
