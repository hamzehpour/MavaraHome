# CHANGELOG — Phase 4 through 8, + follow-ups (ticket template, email login, split architecture, reservation migration)

Full technical detail behind the summary in `README.md`'s checklist. Schema
went from v6 to v7 (additive only — see `database/schema.py`, every change
is `CREATE TABLE IF NOT EXISTS` or `ALTER TABLE ADD COLUMN`, nothing
dropped or rewritten).

## "حساب من" first in the mobile menu, with a hint of what it's for

**Why:** requested — on mobile, "حساب من" was the last item in the
hamburger menu like any other nav link, with no indication it's where a
buyer tracks their reservations (as opposed to a static info page like
the rest of the menu). Desktop's order and plain label stay exactly as
they were — this is mobile-menu-only.

- `loadHeader()` (site.js) tags the account link with a
  `nav-account-link` class and appends a `nav-account-hint` span —
  " (پیگیری و مشاهده رزروها)" — inside the anchor, always in the DOM.
- New CSS: `.nav-account-hint{display:none}` by default (so desktop's
  `innerText` is plain "حساب من", unchanged); inside the existing
  `@media(max-width:768px)` block, `display:inline` (hint visible) and
  `.nav-account-link{order:-1}` (moves it to the front of the mobile
  menu's flex column — everything else keeps its default order, so
  their relative order among themselves doesn't change).
- Real text in the DOM rather than CSS `content` — stays selectable and
  reachable to assistive tech wherever it's actually shown, rather than
  being pseudo-element decoration.

Verified with Playwright at both viewport sizes: desktop keeps "حساب
من" last, unlabeled, at `order:0`; the mobile hamburger menu (screenshot
checked) shows "حساب من (پیگیری و مشاهده رزروها)" as the first item,
with the rest of the menu following in its original order.

## Remove the Telegram-only reject "grace period" — reject is now direct/final everywhere

**Why:** requested — now that "نیازمند اصلاح" exists for "something's
fixable, don't reject outright," the old two-step grace period
(`awaiting_buyer_confirmation`: seat stays held, buyer gets Telegram
buttons to accept the cancellation or dispute it, admin makes a final
call on a dispute) is redundant, Telegram-only, and was the direct cause
of the previous bug report (silently unreachable for a website-only
buyer). Removing it makes Telegram's reject action exactly the same
logic as the website admin panel's: reject is immediate and final.

- Deleted `handlers/reject_confirmation.py` entirely (buyer accept/
  dispute buttons, admin dispute-resolve keyboard, the "resend receipt
  while disputed" mini-flow) and its registration in `bot.py`.
- Deleted `states/dispute_states.py`; removed the now-unused
  `ResendReceiptStates.awaiting_new_receipt` (kept
  `awaiting_correction_receipt`, still used by the needs_correction
  resubmission flow).
- Removed `reservation_service.mark_awaiting_buyer_confirmation()` and
  `finalize_rejection_if()`/`finalize_rejection()` (the dead-since-before
  wrapper).
- `reject_reservation()` is now THE reject action everywhere, and is
  atomic-guarded like `approve_reservation()` (`set_status_if_any`,
  `WHERE status IN (...)`) — a double-tap correctly reports "already
  processed" (`None`) instead of silently re-sending the rejection email
  a second time, which the old unconditional version could do. The
  website's reject endpoint now checks for this and returns 409, matching
  the approve endpoint's existing shape.
- `handlers/admin_reservations.py`'s `_apply_rejection()` collapsed to
  one path: reject, then notify on every channel available — a plain
  Telegram DM (no buttons — nothing left to decide) if the buyer has one,
  and always by email — reporting the real combined outcome to the admin
  (both delivered / Telegram only / email only / neither).
- Removed the now-dead texts/keyboards that only served the grace period
  (`reject_notice_to_buyer`, `REJECT_CONFIRM_*`, `DISPUTE_*`,
  `RESERVATION_CANCELLED_BY_BUYER`, `RESERVATION_FINAL_REJECTED`,
  `ASK_NEW_RECEIPT_PHOTO`, etc.) — kept everything the reason-collection
  step still uses (`ADMIN_REJECT_REASON_MENU`,
  `RECEIPT_PROBLEM_PRESET_REASON`, ...) and every reference to the
  `awaiting_buyer_confirmation` *status string* itself in capacity-
  counting SQL and status-label maps, since those stay correct for any
  historical row already in that state.

**Operational note:** if any reservation is currently sitting in "در
انتظار پاسخ خریدار" (`awaiting_buyer_confirmation`) at deploy time, its
old Telegram accept/dispute buttons will stop responding (the handlers
are gone) and neither admin UI currently offers an action button for that
status — resolve any such reservation (approve or reject it) BEFORE
deploying this change, or it'll need a direct database fix afterwards.
This is very unlikely to apply (the grace period was rarely reached even
before today), but worth a quick check.

Verified locally: full 48-test suite passes (49 minus one test for the
removed dispute-approval fix, one other rewritten for the new direct-
reject shape); the scratch test's reject-related checks updated to match
(reject now returns `None`/final-status instead of transitioning through
`awaiting_buyer_confirmation`); real HTTP round-trip against a local
`ENV=test` server confirms a first reject succeeds (200, status
`rejected`) and a second (double-tap) correctly returns 409.

## Fix: rejecting via Telegram left a website-only buyer stuck, never notified

**Why:** reported — rejecting a reservation from Telegram showed "⚠️ رزرو
رد شد ولی ارسال پیام به خریدار ناموفق بود (آیدی تلگرام: None)" and the
buyer never heard anything, by email or otherwise. Telegram's reject flow
(`mark_awaiting_buyer_confirmation()`) is a grace period on purpose: the
seat stays held while the buyer gets an interactive DM with "می‌پذیرم" /
"توضیح می‌دهم" (dispute) buttons, and only their tap resolves it. That's
meaningless for a website-only buyer with no Telegram account — there's
no chat to put those buttons in, so the reservation was silently stuck in
`awaiting_buyer_confirmation` forever, waiting on a button click that
could never come, and the buyer got nothing at all (this flow never sent
email, unlike the website admin panel's own reject action).

- `handlers/admin_reservations.py`'s `_apply_rejection()` now checks for
  a `telegram_id` FIRST: if the buyer has one, the existing grace-period/
  dispute flow is unchanged; if not, it rejects the reservation directly
  and finally — same shape as the website admin panel's reject action —
  and emails them the reason instead.
- `reservation_service.reject_reservation()` now returns whether the
  rejection email actually went out (previously `-> None`, silently
  assumed), so the Telegram admin sees the real outcome instead of
  guessing — same pattern `approve_reservation()` already used.
- Approve was already correct for this case (checked, per request) — it's
  emailed a website-only buyer their confirmation since an earlier fix
  this session; nothing to change there.

Verified locally: full 49-test suite passes; a dedicated scratch test
confirms `reject_reservation()` on a website-only (no telegram_id) buyer
rejects immediately (not `awaiting_buyer_confirmation`) and reports the
real email-send outcome.

## Fix two "نیازمند اصلاح" bugs: silent correction messages from the alerts channel, admin locked out afterwards

**Why:** reported, after the "نیازمند اصلاح" action shipped — two separate
bugs, both real:

**Bug 1 — typing the correction message from the alerts channel silently
went nowhere.** Tapping "نیازمند اصلاح" on a reservation alert posted in
the admin ALERTS channel/group (not a private chat) set the FSM state on
*that chat* and asked the admin to reply there. If the destination is a
genuine Telegram channel (not a group), a member's typed reply never even
reaches the bot as a normal message — Telegram delivers it as a
`channel_post`, attributed to the channel itself with no `from_user` at
all, which aiogram's `@router.message()` handlers structurally cannot
see. Even in a group, this was still asking for the reply in the wrong
place. Fixed by always collecting free-text follow-ups (the correction
message, and — same bug — a custom typed reject reason, and the optional
post-approval note) in the admin's own private chat instead, regardless
of where the button was tapped: `handlers/admin_reservations.py` now
builds a DM-scoped `FSMContext` via `StorageKey(chat_id=admin_id, ...)`
(the same pattern `handlers/overflow_requests.py` already used for a
similar cross-chat case) and prompts with `bot.send_message()` there. A
small toast on the original button tap ("توضیح اصلاح را در چت خصوصی ربات
بنویسید") tells the admin where to look; if they've never opened a DM
with the bot at all, they get a clear alert instead of silence.

**Bug 2 — every action disappeared once a reservation left
pending_review.** `needs_correction` was only ever a one-way street: once
set, approve/reject/needs-correction all required `expected_status ==
'pending_review'` specifically, so nothing else could ever be done with
that reservation from either Telegram or the website admin panel until
the buyer resubmitted a receipt — reported as the admin panel's actions
just vanishing (`canDecide` there was keyed to `pending_review` only).
Per the corrected design: `needs_correction` should only stop the
*time-limited* reservation lock (already true — it reuses the
no-expiry-column-touched status), never the admin's ability to act.
Fixed by widening every action to accept EITHER starting status:
- New `reservations_repo.set_status_if_any()` — the same atomic
  conditional UPDATE as `set_status_if()`, just `WHERE status IN (...)`
  instead of `= ?`.
- `approve_reservation()`'s default `expected_status` is now
  `("pending_review", "needs_correction")` (still overridable — the
  dispute-resolution path still passes its own single
  `"awaiting_buyer_confirmation"`).
- `mark_awaiting_buyer_confirmation()` (Telegram's reject-with-grace-
  period start) and `request_correction()` both accept the same pair now
  — the latter meaning an admin can re-issue a *second* correction
  message (buyer's resubmission still wasn't right, or just more detail)
  without waiting for anything first.
- `pages/admin/reservations.html`'s `canDecide` now includes
  `needs_correction`, restoring all three buttons there.
- No server.py endpoint changes needed — every endpoint already called
  through these same service functions.

**Also requested:** the "نیازمند اصلاح" email now asks the buyer to reply
to that same email with the corrected receipt attached (so an admin can
review and decide from their inbox), instead of only pointing them back
to the website — the automated website/Telegram resubmission still works
and is mentioned as an alternative. Note this is a `DEFAULT_SETTINGS`
text change — `migrate.py`'s `INSERT OR IGNORE` won't overwrite a row
that's already been seeded, so an environment that already ran migrate.py
since the 4-step redesign shipped needs this one template pasted in by
hand via Settings (Telegram menu or the website settings page) to pick up
the new wording.

Verified locally: full 49-test suite passes; a dedicated scratch test
covers re-issuing a correction from `needs_correction`, rejecting
directly from it, and approving directly from it (previously all three
would have failed the atomic status check and silently no-op'd). Also
re-ran the exact sequence over real HTTP against a local `ENV=test`
server: submit receipt → needs-correction → needs-correction again
(admin_note updates) → approve directly, and separately submit receipt →
needs-correction → reject directly — both fully succeeding end to end.

## Fix: "تکمیل رزرو" button/countdown stayed after successfully completing a resumed reservation

**Why:** reported, right after the resume feature above shipped — after
resuming a reservation and uploading its receipt, closing the modal
still showed the exact same "تکمیل رزرو" button and a countdown ticking
toward a lock that no longer applied (the reservation had already moved
to `pending_review`, which never expires). The account.html/event-
detail.html card was drawn from the reservation's status as it was
*before* the modal opened, and had no way to find out the status had
just changed underneath it.

- `resumeReservationModal(record, onDone)` now takes an optional
  callback, fired the instant the receipt upload actually succeeds (see
  `submitReceiptStep()`) — not on modal close, so the page behind it
  updates immediately, even before the buyer dismisses the success
  screen.
- `account.html` passes `() => renderDashboard()` — the whole reservation
  list re-fetches and redraws, dropping the resume card the moment its
  status changes.
- `event-detail.html` (via `initEventDetail()` in site.js) passes
  `() => initEventDetail()` — the CTA swaps back to the normal "رزرو
  بلیت" the instant the reservation leaves `pending_payment`.
- A fresh (non-resumed) booking never sets `onDone`, so nothing extra
  happens there — there's no prior on-page state tied to a reservation
  that didn't exist yet.

**Also caught while investigating:** the new `payment_reminder_minutes`
setting and the four new email templates (`tmpl_email_payment_reminder_*`,
`tmpl_email_needs_correction_*`) added by the 4-step redesign were never
actually seeded into the already-deployed production database — `DEFAULT_SETTINGS`
is only inserted via `database/schema.init_db()`'s `INSERT OR IGNORE`, which
runs from `migrate.py`, not automatically on every `api.server`/`bot.py`
start. The redesign didn't bump `SCHEMA_VERSION` (no new columns), so the
earlier deploy instructions said `migrate.py` wasn't needed — true for
the schema itself, but not for these new *settings rows*, which were
consequently missing until `migrate.py` is actually run once. Until then,
the payment-reminder and needs-correction emails would go out with an
empty subject/body. **`migrate.py` needs to be run once** on production
to backfill these (safe/idempotent, no data loss — confirmed locally: an
existing test database missing the new keys had them filled in
correctly by a `migrate.py` run, with `payment_expiry_minutes` — already
present — left untouched).

Verified locally: full 49-test suite still passes. Playwright re-ran
both resume paths end-to-end and confirmed the underlying page updates
immediately after a successful receipt upload, before the modal is even
closed — the account.html card lost its resume button/countdown, and
the event-detail.html CTA reverted to the normal "رزرو بلیت" button.

## Resume an unfinished reservation instead of starting over

**Why:** requested, right after the 4-step redesign above shipped — a
buyer who closes the tab mid-payment (goes to their banking app, gets
interrupted, whatever) had no way back to that exact reservation. They'd
either abandon it (fine — it expires on its own) or start a brand new
one, which is the thing the capacity lock exists to prevent duplicates
of.

- `pages/account.html`: a `pending_payment` reservation in "رزروهای من"
  now shows a live countdown (against its real `expires_at`) and a
  "تکمیل رزرو" button, styled with a new `.btn--resume` amber accent —
  distinct from the gold "book" button and the navy outline "details"
  button, so it visibly reads as "you have something waiting."
- `pages/event-detail.html`: a logged-in customer with an unfinished
  reservation for *that* event sees the same "تکمیل رزرو" button + live
  countdown in place of the normal "رزرو بلیت" CTA — falls back to the
  normal CTA silently if they're not logged in or the check fails, so
  this is only ever additive.
- Both call the same new `resumeReservationModal(record)` (site.js):
  reopens the booking modal for that exact reservation and jumps
  straight to the receipt-upload step (step 4) — everything before that
  (session, buyer info, payment instructions) was already shown once
  when the reservation was first created, so only the actual missing
  piece is asked for again. The amount due and payment card are repeated
  as a compact reminder right there, since a resumed session may never
  have shown step 3 on this page load.
- The countdown itself (`startCountdown()`) was generalized from a
  single-slot modal-only timer into something reusable — needed since
  account.html can show more than one unfinished reservation, each
  ticking down independently, which the old single-timer version
  couldn't do at all.

**Bug fixed along the way:** `GET /account/reservations` never actually
included `event_id` on any row — `list_for_user()`'s raw query has no
such column (it only has `session_id`), and `get_ticket_context()`
(built for the ticket PDF, which never needed the id) doesn't resolve or
return one either. Both new "resume" entry points depend on matching a
reservation to its event, so this would have silently done nothing
(every match failing against `undefined`) without a session lookup added
to the endpoint's own enrichment step — caught by the first end-to-end
Playwright run of the account.html path, which showed the dashboard
correctly but the "تکمیل رزرو" flow going nowhere.

Verified locally: full 49-test suite still passes. Playwright drove both
new entry points end-to-end against a local `ENV=test` server — logged
in, saw the live countdown and resume button on account.html, resumed
straight into the receipt step with the correct amount/card shown,
uploaded a receipt, and got the normal success screen; separately,
loaded event-detail.html while logged in with an unfinished reservation
for that event and confirmed the amber "تکمیل رزرو" CTA (not the normal
gold one) with its own live countdown, resuming the same way from there.

## Booking-flow redesign: real 4-step flow, capacity lock actually works again, "نیازمند اصلاح" admin action

**Why:** requested — the capacity lock (`payment_expiry_minutes`) had been
in the code for a while but stopped doing anything useful. A prior
redesign (see the removed comment in `site.js`) collapsed reservation-
creation and receipt-upload into one atomic step "for simplicity," which
meant `expires_at` was set and then immediately irrelevant — there was
never a window where a reservation existed *without* its receipt already
attached, so the lock never actually held a seat against anything. On
top of that, there was no way for an admin to say "I can't approve this,
but I don't want to reject it either" (wrong receipt, wrong amount,
illegible photo) — only a binary approve/reject.

**Booking flow, now four real steps** (`website/assets/js/site.js`):
1. "رزرو بلیت" button → date/session picker (unchanged).
2. Name/phone/email + seat count (`bkForm`, payment fields removed).
3. Submitting step 2 is what actually creates the reservation
   (`createReservationAndLock()`) — this is the real, only moment the
   lock starts. Step 3 (`bkLockBlock`) shows the payment card and a live
   countdown against the reservation's real `expires_at` (now returned by
   `/reservations`, `/admin/reservations` etc.), reading
   `payment_expiry_minutes` from the new `/payment-info` field instead of
   a hardcoded number.
4. Mandatory receipt upload (`bkReceiptBlock`, reusing the existing
   accessible file-picker), which can now genuinely fail/retry without
   losing the reservation — it already exists by this point.
   Waitlist signups (no seat to lock or pay for) keep their original,
   unchanged review→submit path.
- `payment_expiry_minutes` default lowered from 15 to **10** minutes;
  new `payment_reminder_minutes` (default **5**) setting.
- New `reservation_service.send_payment_reminders()`: a one-time email
  nudge ("۵ دقیقه دیگر فرصت دارید") for any `pending_payment` reservation
  past the reminder threshold, dedup'd via the `logs` table. Runs from
  both `run_expiry_loop` (bot process) and `run_expiry_loop_sync` (API
  process) since it's plain SMTP, not a Telegram DM — works even when
  bot.py isn't running. New admin-editable templates:
  `tmpl_email_payment_reminder_subject`/`_body`.
- **New admin action, "نیازمند اصلاح"**, alongside approve/reject — on
  both the Telegram review keyboard and the website admin panel
  (`pages/admin/reservations.html`). Sends a required text message to the
  buyer (email + Telegram DM if linked) and moves the reservation to a
  new `needs_correction` status — no time limit while it sits there
  (`reservations_repo.list_expired_pending` only ever matches
  `pending_payment`, so this never auto-expires). The buyer resubmits a
  receipt the same way as the first time (`submit_receipt()` now accepts
  `needs_correction` as a starting status too, alongside
  `pending_payment`), landing back on `pending_review`.
  New template: `tmpl_email_needs_correction_subject`/`_body`.
- Buyer-side resubmission for a `needs_correction` reservation: an
  "ارسال رسید جدید" button in Telegram's "رزروهای من" and a file-upload
  block in `pages/account.html`, both calling the same `submit_receipt()`
  path.
- New endpoint `POST /admin/reservations/<id>/needs-correction`; `admin_note`
  and `expires_at` are now exposed on every reservation the admin/account
  APIs return (repurposed per status — rejection reason when rejected,
  the correction message when `needs_correction`).

No schema/migration change — `needs_correction` reuses the existing
free-text `status`/`admin_note` columns, and the reminder's one-time-send
tracking reuses the generic `logs` table, same as the (now-removed)
review-reminder feature did.

**Bug fixed along the way:** `send_payment_reminders()`'s first draft
compared `created_at` (SQLite's own `datetime('now')`, space-separated,
no offset) against a Python-side `isoformat()` cutoff (`...T...+00:00`)
— two different string shapes that don't sort against each other
correctly, so the very first version fired a reminder for a
brand-new reservation immediately. Fixed by computing the cutoff with
SQLite's own `datetime('now', '-N minutes')` so both sides of the
comparison are generated the same way.

Verified locally: full existing 49-test suite still passes; a dedicated
scratch test exercised `submit_receipt()` from both starting statuses,
`request_correction()`'s transition/dedup/admin_note, and
`send_payment_reminders()`'s threshold + dedup (including the timestamp-
format bug above, caught by the test before the fix). Also verified
end-to-end over real HTTP against a local `ENV=test` server + a
Playwright run of the actual 4-step browser flow: session pick → step 2
form → reservation created with a real `expires_at` → step 3's live
countdown renders correctly against it → step 4 receipt upload (rejects
a missing file, accepts an image) → `pending_review`. Then, via the raw
API: admin `needs-correction` action → `needs_correction` with the
correction message in `admin_note` → buyer resubmission via
`POST /reservations/<id>/receipt` → back to `pending_review`.

## Split the admin alerts channel from the sales-monitoring channel

**Why:** reported, live — the monitoring channel (silent per-day board,
`services/channel_service.py`) and the new-request alerts (fresh
message + approve/reject buttons, added earlier this week) were
sharing one setting, `monitoring_channel_id`. The alerts feature was
built by reusing whatever channel the admin had already configured for
monitoring, since it existed and was already tested — but that meant
once an admin actually set monitoring up, every reservation produced
*two* messages in the same channel: one silently edited into the
board (no notification), one fresh actionable alert (does notify) —
easy to mistake for a duplicate/bug rather than two different features
that happened to collide.

- New setting `admin_alerts_channel_id`, independent from
  `monitoring_channel_id` — `settings_service.notify_admin_channel()`/
  `notify_admin_channel_with_receipt()` now read this one instead.
- `handlers/channel_setup.py`'s `_configure_monitoring_chat()`
  generalized into `_configure_channel()` (takes the setting key, log
  action, and whether to trigger the board backfill — only the
  monitoring channel has a board to backfill), used by both setups.
- New parallel setup flow for the alerts channel: a
  "🔔 راه‌اندازی کانال هشدار رزرو" menu button (forward-a-message, same
  as monitoring) and a `/setalertsgroup` command (for a group, same
  reasoning as `/setgroup` — forwarding an ordinary group message
  never carries the group's own chat id, only the sender's).
- An admin can still point both settings at the same channel if they
  want everything in one feed — this makes it a deliberate choice
  instead of the only option.

Verified locally: `notify_admin_channel()` now reads and delivers to
`admin_alerts_channel_id` specifically (confirmed against a different
value than `monitoring_channel_id` in the same test), and
`channel_service.py`'s board is confirmed unchanged, still reading
only `monitoring_channel_id`.

## Removed: the repeating "رزرو همچنان منتظر بررسی است" staff reminder

**Why:** requested — disable it entirely.

Found the flow: `utils/scheduler.py`'s `run_expiry_loop` (every 120s)
called `_send_review_reminders(bot)`, which DM'd every staff member
with payment-approval permission once a `pending_review`/
`awaiting_buyer_confirmation` reservation sat unactioned past
`review_reminder_minutes`, then repeated every
`review_reminder_repeat_minutes` until resolved.

Removed the function and its call site entirely (not just disabled —
there's nothing left to accidentally re-enable), and removed the two
settings that only ever configured it (`review_reminder_minutes`,
`review_reminder_repeat_minutes`) from `EDITABLE_SETTINGS`,
`SETTINGS_FIELD_TYPES`, `SETTINGS_INT_RANGE`, `DEFAULT_SETTINGS`, and
the website settings page's "رزرو و پرداخت" section — an admin would
otherwise still see a working-looking control for a feature that no
longer does anything. (A stale settings row from before this change
may still sit harmlessly in the production DB; nothing reads it
anymore.)

Verified: `_send_review_reminders` no longer exists on the scheduler
module, and both removed keys are confirmed absent from
`EDITABLE_SETTINGS`.

## Small pulsing green dot on every "در حال اجرا" (live) event badge

**Why:** requested — make an ongoing event easier to spot at a glance
among a grid/slider of cards.

`badgeHTML()` in `site.js` is the single function every event card on
the public site renders its status badge through (homepage slider,
homepage "upcoming" preview, the events grid page) — one change there
covers all of them, no per-page duplication. Reused `.live-dot` as-is
(the same small pulsing dot already used on about-mansour.html's
"Mansour is live now" pill) rather than building a new indicator, so
it's the one consistent "something is live right now" signal across
the site, not two similar-but-different dots.

Verified with Playwright, light and dark theme: the dot renders
correctly on the events grid page and the homepage slider/preview
cards, only for `status === 'ongoing'` — "به‌زودی"/"آرشیو" badges
unaffected.

## Approval confirmation email now has the PDF ticket attached

**Why:** requested — the ticket (QR code) was only reachable via a
Telegram photo or by logging into the website account page; a buyer
who only ever used email had no direct way to get it.

- `utils/email_sender.send_email()` gained an optional `attachments`
  parameter — a plain `MIMEText` when there's nothing to attach
  (every existing call site, unchanged wire format), a `MIMEMultipart`
  with the PDF as an `application/pdf` part when there is.
- New `reservation_service._build_ticket_pdf_bytes()`: builds the same
  PDF the website's own `ticket.pdf` download already produces, and
  is wired into both places that send an "approved" email —
  `approve_reservation()` (normal review-and-approve) and
  `approve_waitlist_entry()` (waiting-list approval). Best-effort: any
  failure building the PDF (missing logo file, reportlab error, etc.)
  logs and sends the email without the attachment rather than blocking
  the approval or the notification entirely.
- Moved `_ticket_context`/`_resolve_media_path` out of `api/server.py`
  (where they were module-private) into `services/ticket_service.py`
  as `get_ticket_context`/`resolve_media_path`, so the bot-process side
  (`reservation_service.py`) and the website's own ticket.pdf endpoint
  now share one assembly function instead of two that could drift
  apart — a straight move, `api/server.py`'s two call sites updated,
  behavior unchanged.

Verified locally: a real approval produces a valid PDF (`%PDF` header,
opens with actual event/QR content) attached to the console-printed
email (no SMTP configured locally) for both the normal-approval and
waiting-list-approval paths; the website's `/ticket.pdf` download
endpoint re-tested end-to-end (real OTP login, real download) after
the `_ticket_context` move to confirm it wasn't broken by the refactor.

## Booking form: payment receipt is now required, custom-styled, and its errors are visible

**Why:** requested — the receipt was optional, but a customer skipping
it left the admin no proof of payment to review against. Separately: a
real UI bug — the file-type/size error rendered in `bkFormError`, a box
at the very *top* of the modal, while the receipt field sits further
down; on mobile, once the buyer had scrolled to reach it, the error
appeared off-screen above the fold and went unnoticed.

- The receipt file is now required for a normal booking (unchanged for
  a waiting-list signup — there's no confirmed seat to pay for yet, so
  the whole payment section stays hidden there, same as before).
- New dedicated `#bkReceiptError` box directly under the file picker
  (not the shared top-of-form box) — and shown via `scrollIntoView()`,
  so it's never off-screen. Reused `.bk-form-msg--error`, the site's
  existing error style, rather than inventing a new one.
- The plain `<input type="file">` — bare browser chrome, no visual
  connection to the site — is now a custom `.bk-file-*` component: a
  pill-styled label button (matching `.bk-chip`'s visual language:
  `var(--bg-soft)`/`var(--border)`, gold on selection) plus a filename
  display, built on the standard clip-rect technique (the native input
  stays in the DOM and keyboard/screen-reader operable, just visually
  replaced by the label) rather than `display:none`, which would break
  both. Deliberately validated in JS rather than via `required` on that
  native input — a browser's validation bubble anchored to a visually
  hidden 1px element lands in an inconsistent spot across browsers,
  which would have reintroduced a version of the same "error rendered
  somewhere the buyer doesn't look" bug this was fixing.
- Label copy: "رسید پرداخت (اختیاری)" → "ارسال رسید پرداخت" (and the
  hint text below it), since it no longer is optional.

Verified with Playwright at a mobile viewport (400×900): submitting
with no file shows the required error positioned right under the file
picker (not the top box, confirmed via bounding-box diff) with zero
scrolling needed; oversized/wrong-type files show their existing
errors in the same spot; selecting a valid file clears the error and
lets the booking proceed; screenshotted in both light and dark theme.

## The "email was sent" admin message now reflects the real outcome

**Why:** found immediately after shipping the previous fix (which
assumed "buyer has an email on file" meant "the email went out") — a
real production SMTP auth failure (Gmail rejecting the configured app
password, unrelated to this code) showed the gap: the admin was told
"✅ ... تأییدیه از طریق ایمیل برایش ارسال شد" for a reservation whose
email had actually just failed to send.

- `_notify_customer_by_email()` now returns whether `send_email()`
  actually succeeded, instead of nothing.
- `approve_reservation()` returns that as a third tuple element,
  `(code, qr_image, email_sent)` — the two Telegram-side callers that
  unpack it (`admin_reservations.py`, `reject_confirmation.py`) updated
  accordingly; the two website API callers were untouched since they
  never unpacked past `result is None` in the first place.
- The admin-side message for a website-only buyer (no Telegram) now
  branches on the real `email_sent` value, not "does this buyer have an
  email" — so a genuine SMTP failure surfaces as an honest "ارسال ایمیل
  ناموفق بود ... لاگ سرور را چک کنید" instead of a false "ارسال شد".

(Separately: the actual SMTP failure hit in production was Gmail
rejecting `mavarahome.me@gmail.com`'s configured password with `535 —
Username and Password not accepted` — an app-password/2FA setup issue
on the Google account, not a code bug; see the chat for the fix.)

## Admin channel alert now includes the receipt + approve/reject buttons (schema v15)

**Why:** requested, right after seeing the plain-text alert land — an
admin wanted to act directly from the channel (approve/reject a payment)
the same way the existing Telegram-only staff DM already lets them
(`handlers/payment.py`), instead of the channel message being read-only
and needing a trip elsewhere to actually do anything.

- `bot_outbox` gained two nullable columns, `reservation_id` and
  `photo_ref` — a plain "text" message (the waitlist alert, which has no
  receipt) leaves both NULL, unchanged from before.
- New `kind="receipt_review"` outbox item: delivered by
  `utils/scheduler._deliver_receipt_review()`, which sends the receipt
  as a photo with the alert as its caption and the same
  `reservation_review_keyboard()` the DM uses. `photo_ref` is a prefixed
  reference — `"tg:<file_id>"` for a receipt submitted through the
  Telegram bot (Telegram already has it, reused as-is), `"file:<relative
  path>"` for one uploaded through the website (read from
  `private_media/` and uploaded fresh, since a bare path is meaningless
  to Telegram's API — only an actual upload is).
- `settings_service.notify_admin_channel_with_receipt()`: same
  channel/no-op-if-unset shape as `notify_admin_channel()`, enqueues the
  new kind instead of plain text.
- The existing approve/reject callback handlers needed no changes at
  all — `admin_reservations.py`'s `_safe_ack_admin_message()` already
  handled being invoked on a photo-caption message (it was written for
  the DM case, which is also a photo), and permission is checked by who
  clicked, not which chat the button was clicked in.

Verified locally: a website-submitted receipt (`file:` prefix) and a
Telegram-submitted one (`tg:` prefix) both produce the correct
`bot_outbox` row; `_deliver_receipt_review()` against a mock bot
confirmed the local-file path resolves to a real, existing file and
builds an `FSInputFile`, the Telegram case passes the file_id straight
through as a string, and both produce the correct approve/reject
callback_data for their reservation id.

## Fixed: monitoring channel setup didn't work for a Telegram *group*

**Why:** hit live, during setup — the forward-a-message flow
(`handlers/channel_setup.py`) only ever worked for an actual Telegram
*channel* (or a supergroup post sent anonymously "as the group").
Forwarding an ordinary message sent by a group *member* carries
`forward_from` (that member), never `forward_from_chat` — Telegram
gives no way to recover "this came from group X" from that kind of
forward at all, so the admin's group could never pass, no matter how
carefully the forward was done ("چرا جلوش نوشت [my own name]! این از
کانال نیست" was Telegram behaving correctly, just for a flow that
assumes a channel).

- New `/setgroup` command, sent directly inside the group (not via the
  bot's private chat): needs no forward at all — a bot command always
  reaches the bot regardless of the group's privacy-mode setting, and
  `message.chat.id` inside the group already IS the group's id.
- Both routes (forward-from-channel, `/setgroup`-in-group) now call one
  shared `_configure_monitoring_chat()` so they save the same setting,
  log the same way, and trigger the same reservation backfill —
  previously only the forward path existed to duplicate.
- Updated the setup instructions and the "not a forward" error message
  to point at `/setgroup` as the group alternative, so this doesn't
  strand the next admin who reaches for a group instead of a channel.

## Fixed: deploy/mavara-bot.service and mavara-api.service pointed at a stale path

Both templates still said `/opt/mavara-bot` / `User=mavara` — the
production server actually runs everything under `/opt/MavaraHome/bot`
as root (confirmed via `systemctl show mavara-api` on the real deploy).
mavara-api.service's installed copy on the server was already correct
(someone fixed it there without updating this repo's copy); this brings
both templates in line with reality so `mavara-bot.service` can actually
be installed from this repo directly, and future reference to either
file isn't misleading.

## Instant Telegram channel alert for new reservations + waitlist entries

**Why:** requested — admins wanted to know about a new reservation
needing review, or a new waiting-list signup, immediately (not by
periodically checking the bot/website), to cut the lag between a
request coming in and someone actually looking at it.

Found existing, working infrastructure to build on rather than
inventing a new "channel setup" flow: `handlers/channel_setup.py`
already lets an admin configure `monitoring_channel_id` by forwarding
any message from that channel (reliable ID resolution, no public
username needed), for `services/channel_service.py`'s live per-day
reservation board. That board only ever *edits* an existing message in
place, though — Telegram doesn't push a notification for message edits
— so it was never actually useful as an alert, only as a dashboard
someone has to think to open. This reuses the same channel + setting,
adding a brand-new message (which Telegram does notify for) at the two
moments an admin actually needs to know something happened:

- A reservation reaches `pending_review` (buyer submitted a payment
  receipt) — `reservation_service.submit_receipt()`.
- A new waiting-list entry is created (session was full) —
  `reservation_service._create_reservation_for_user()`.

Both call sites are the single shared functions already used by BOTH
the Telegram bot and the website booking flow, so the alert fires
regardless of where the request came from — no per-caller duplication,
and no risk of the website path silently going unnotified the way
`handlers/payment.py`'s existing photo+approve-buttons DM already does
today (it's wired only into the Telegram receipt handler; a receipt
uploaded from the website never reaches it, since `api/server.py` has
no live aiogram `Bot` instance to send with). That existing DM stays
untouched — it's still the actionable path for staff who can approve
payments; the new channel message is a broader, read-only heads-up for
everyone in the channel.

New `settings_service.notify_admin_channel(text)`: reads
`monitoring_channel_id`, no-ops if unset, otherwise enqueues through
`bot_outbox` — not a direct `bot.send_message()` — because
`reservation_service.py` runs inside both the bot process and the
website API process, and only the bot process holds a live `Bot`
instance (delivery happens via `utils/scheduler.py`'s existing
`run_outbox_loop`, same as OTP codes and admin chat replies).

**Operational note, not yet confirmed:** this only works if the bot
process (`bot.py`) is actually running as its own long-lived process in
production — nothing in this repo's CHANGELOG/README history shows it
ever being deployed as a systemd service the way `mavara-api` is
(every prior deploy in this project only ever restarted `mavara-api`).
If `bot.py` isn't running, `bot_outbox` rows will queue forever and
never actually send, silently. Needs checking before this is relied on.

Verified locally: `notify_admin_channel()` enqueues correctly into
`bot_outbox`; full reservation → receipt → alert flow and full
waitlist-signup → alert flow, both via the website-originated call path
and the Telegram-originated one, produce correctly formatted Persian
alert text (event, date/time, buyer, count, source) and the right
source label either way.

## Per-event ticket price now editable from the events admin page

**Why:** reported — the settings page's "قیمت هر بلیت" (ticket price)
lived under general settings, implying one global price, but pricing is
really per-event (`event_service.get_effective_price()` already checked
each event's own `ticket_price` column before falling back to the
settings default — the backend always supported this) and the events
admin page had no field to actually set it. So every event was silently
using the global default; there was no way to give one event its own
price without editing the database directly.

- `website/pages/admin/events.html`: new "قیمت اختصاصی بلیط این رویداد"
  field on the event form. Empty = no override, falls back to the
  settings-page default; a number = this event's own price. Round-trips
  correctly through create, edit, and clearing back to empty.
- `_event_public()` (api/server.py) now also returns the raw, nullable
  `ticket_price` column alongside the existing resolved `price` — the
  admin editor needs to tell "no override" apart from "this event's
  price happens to equal today's default", which the resolved value
  alone can't distinguish.
- The create endpoint's wire field for this was inconsistently named
  `price`; PATCH (which forwards raw field names to the DB column
  whitelist) already expected `ticket_price`. Create now accepts
  `ticket_price` primarily (matching PATCH and the DB column), keeping
  `price` only as a fallback so nothing that already sent it breaks.
- Relabeled the settings-page field to "قیمت پیش‌فرض بلیت... فقط برای
  رویدادهایی که قیمت اختصاصی ندارند" so it reads as a fallback default,
  not "the" price.

Found in passing, not fixed (out of scope of this request, flagging for
later): `DELETE /api/v1/admin/events/<id>` has no backend route at all —
the events page's 🗑️ delete button calls it and gets a 404. Pre-existing,
unrelated to this change.

Verified locally: created an event with a custom price (both `price` and
`ticket_price` correctly 777000 in the response) and one without (falls
back to the global default, `ticket_price` correctly null); cleared a
previously-set price via PATCH and confirmed it reverts to the default;
full Playwright pass through the actual admin UI — create with a price,
reopen and see it prefilled, clear it, reopen and see it empty — zero
console errors.

## "Maximal admin independence," phase 3 — site content + brand images

**Why:** the last two pieces of the original story — "اطلاعات فیکس روی
سایت مثلا توی فوتر و اینها" (fixed site info like the footer) and
"تصاویر سایت مثل لوگو" (site images like the logo). Scoped down from
the full ~150-key I18N table (button labels, error messages, UI
microcopy — never really "fixed info", and editable wrong could break
UX clarity) to what's actually informational content: footer tagline
and copyright, the founder's bio (about-mansour page), the about/
companion page paragraphs, contact info, and the homepage's rotating
quotes. English copy stays hardcoded — out of scope for this phase.

- 13 new `content_*` settings (same `EDITABLE_SETTINGS`/`settings` table
  mechanism, Persian-only) seeded with the exact text that was already
  hardcoded, so nothing changes until an admin edits something.
- New public, unauthenticated `GET /api/v1/site-content` — deliberately
  scoped to just these 13 keys (via `settings_service.CONTENT_KEYS`),
  never the full settings table, so no other setting has to be reasoned
  about as "safe for anonymous visitors" key by key.
- `site.js`'s new `loadSiteContent()` fetches that endpoint on every
  page load, merges the result into `I18N.fa`, then re-runs the existing
  `applyLang()`/`loadFooter()` — no per-page HTML changes needed since
  the affected text already used `data-i18n` attributes or (footer only)
  a regenerable template function. Found and fixed a real bug while
  testing this: it first called through `app.js`'s `API` object, which
  doesn't exist on `contact.html`/`about-mavara.html`/`companionship.
  html`/`podcast.html` (they don't load `app.js` at all) — those pages
  silently kept stale default text. Switched to a raw `fetch()` with no
  dependency on `app.js`, verified working on all four.
- Brand images (header logo, favicon, social-share preview) turned out
  to already be plain static files at fixed paths the HTML hardcodes —
  no templating needed. `/api/v1/admin/upload` gained 3 new `kind`
  values (`brand_logo`/`brand_favicon`/`brand_og_image`) that overwrite
  those exact files in place instead of saving under a random name;
  each requires the format the HTML already expects (PNG for the logo,
  WebP for the other two) so a format swap can't silently break an
  `<link type="...">`/`og:image` tag. Also added a dimension guardrail
  (max 4000×4000px) to the upload endpoint generally — the existing
  Phase-1 guardrail only capped file size, not pixel dimensions, so a
  flat-color 10000×10000 image could still pass under the 3MB cap.
- `settings.html`: new "محتوای سایت" section (generic, same mechanism as
  every other settings section) and a new "تصاویر برند" box with 3
  upload slots + live previews.

Verified locally: seeded all 13 defaults via `migrate.py`; confirmed
`GET /site-content` returns them; edited values via the authenticated
API and confirmed the new text actually renders on the live pages
(including the 4 pages without `app.js`, post-fix); Playwright pass on
the settings page's new section (renders/saves/reverts, no console
errors) and the brand image uploads (correct format accepted and
written in place, wrong format rejected, oversized image rejected);
restored the real logo/favicon files afterward (git checkout) since
testing genuinely overwrote them locally.

## "Maximal admin independence," phase 2 — email templates now admin-editable

**Why:** direct continuation of phase 1. The website settings page (and
the underlying `EDITABLE_SETTINGS`/`settings` table mechanism already
built for Telegram message templates) covered the bot's Telegram
messages, but the 4 emails the system sends — OTP login code, reservation
approved, reservation rejected, waiting-list "no capacity opened up" —
were still hardcoded Python f-strings the admin could not see or change
at all. Migrated all 4 onto the same mechanism, no new infrastructure
needed.

- New `render_email(template_key, **values)` helper in
  `settings_service.py`: reads `tmpl_email_{key}_subject` /
  `tmpl_email_{key}_body` from `settings`, auto-injects `brand_name` into
  every template so nothing has to pass it explicitly, and renders both
  through the same safe `{placeholder}` substitution already used for
  Telegram templates (never crashes on a stray or unknown brace).
- 8 new `tmpl_email_*` keys added to `DEFAULT_SETTINGS` (seeded via the
  existing unconditional `INSERT OR IGNORE` loop in `init_db()` — no
  schema version bump needed, since no table or column changed, just new
  default rows) and to `EDITABLE_SETTINGS`/`SETTINGS_FIELD_TYPES` (subject
  = short text, body = textarea), each label naming exactly which
  placeholders that template supports.
- `reservation_service.py` (`approve_reservation`, `_notify_rejection_email`,
  `approve_waitlist_entry`, `reject_waitlist_entry`) and
  `customer_auth_service.py` (`request_otp`) now call `render_email(...)`
  instead of building the email text inline.
- Website: `settings.html` gets a new "قالب پیام‌های ایمیل" section listing
  the 8 keys — no new code needed beyond that, since the page already
  renders/saves any section generically from the shared `SECTIONS` list.

**Deploy note:** even though `SCHEMA_VERSION` did not change, `migrate.py`
still needs to run in production — the 8 new default rows only get
inserted by `init_db()`'s seeding loop, which only `migrate.py` and
`bot.py` call; `api/server.py` never calls it on its own, so skipping
this step would leave the new settings-page section showing empty fields
until an admin fills every one in by hand.

Verified locally: `render_email()` output checked directly for all 4
template keys with realistic values (Persian text, correct interpolation
of every documented placeholder); confirmed editing a template via
`update_setting_validated` changes the next call's rendered output
immediately; confirmed the new default rows seed via a local `migrate.py`
run; confirmed via the running API (real login, real JWT) that all 8 new
keys appear in `GET /admin/settings` and a `PATCH` persists correctly;
confirmed via Playwright that the new settings-page section renders, the
existing generic save button works with no console/page errors, and the
saved value survives a reload.

## New admin settings page — "maximal admin independence," phase 1

**Why:** requested — the admin should be able to change anything
editable (messages/notices, fixed site info, images) without needing a
developer, within safe guardrails (size/format limits on images,
length/range limits on text). Investigated the whole surface first (see
the plan posted before this work) and started with what already had
working backend infrastructure but no website UI at all: settings,
message templates, bank cards, ticket PDF template, and upload safety.

- **New `website/pages/admin/settings.html`** (+ sidebar link on all
  eight admin pages): general site text (brand name, welcome message,
  rules, support contact), booking/payment numbers (ticket price, max
  tickets per person, payment/review-reminder timers), customer-login
  channel note, the four Telegram message templates (with their
  placeholder hints shown inline), bank card management (add/activate/
  delete, 16-digit validation, Persian-digit and dash/space
  normalization), auto-rotate-cards toggle, and the ticket PDF template
  (title/subtitle/footer + logo upload) — the last of these already had
  a backend endpoint from an earlier phase with no page ever built for
  it.
- **Reused, not duplicated**: this is the *same* `EDITABLE_SETTINGS`
  key/value table the Telegram bot's own settings menu already reads
  and writes — one source of truth, editable from either place.
- **New validation layer** (website-only; the Telegram menu is
  deliberately left exactly as free-text as it always was): numeric
  fields get a real range check, text fields a length cap — see
  `settings_service.validate_setting_value`. A multi-field save is
  all-or-nothing: if one field fails, nothing is written, so a form
  can't end up half-saved with the admin unsure which fields actually
  took.
- **Real correctness bug fixed while building this**: `settings_repo.get()`
  cached values in a process-local dict. Since `api/server.py` (website)
  and `bot.py` (Telegram) are separate OS processes, a setting changed
  in one process (e.g. the ticket price, from the website) kept its
  stale cached value in the *other* process until that process happened
  to restart — directly undermining "admin changes something and it
  takes effect," the entire point of this feature. Removed the cache;
  settings reads aren't hot-path enough for a bare SQLite SELECT to
  matter.
- **Real gap fixed**: `review_reminder_repeat_minutes` was a working
  setting (`utils/scheduler.py` already read it) that was editable
  *nowhere* — not the website, not even the Telegram menu — because it
  had simply never been added to `EDITABLE_SETTINGS`. Now listed, so
  both channels get it.
- **Upload guardrail, previously entirely absent**: `/api/v1/admin/upload`
  used to accept any size, and silently saved anything with an
  unrecognized mime type as `.bin`. Now: unknown mime types are rejected
  outright; a size cap applies (3MB images, 25MB video); and every image
  is opened and verified with Pillow (already a dependency) before being
  saved, so a renamed non-image file can't be uploaded as one.
- **Caught mid-build**: a first pass wired a save button's handler via
  `onclick="saveSection(${JSON.stringify(section.keys)})"` — the
  array's own double quotes closed the outer double-quoted `onclick`
  attribute early, corrupting the handler (the same bug class already
  fixed once this project in `checkin.html`'s `doCheckin` binding).
  Caught by the very Playwright test written to verify the save flow
  (it showed no success/error message at all, plus a page error).
  Fixed the same way as last time: bind via `addEventListener` +
  closure instead of serializing data into an HTML attribute.
- **Verified**: every endpoint exercised directly (curl) and through
  the real admin UI — a non-numeric or out-of-range setting value is
  rejected with the specific field named, a valid save persists and
  survives reload; a 16-digit card (including one typed with Persian
  digits and dashes) is accepted, a too-short one rejected; activating
  a second card correctly deactivates the first; auto-rotate persists;
  a fake "image" (plain text with a claimed `image/png` mime), an
  oversized real PNG, and a genuine small PNG were each handled
  correctly by the upload guardrail (reject, reject, accept); the
  ticket-template logo upload + save round-trips correctly.
- **Deliberately out of scope for this pass** (next follow-ups, not
  dropped silently): migrating the hardcoded Python email subject/body
  strings (OTP, approve/reject) into editable templates; free-text site
  content (footer, nav, page copy) and the image registry (logo/
  favicon/hero swap) from the original plan's phases 3–5; and an
  owner-vs-admin permission split for sensitive fields (card number,
  price) — every current website admin account has the same `role`
  value in practice today, so gating behind a role nobody has yet would
  risk locking out the very account testing this right after deploy;
  the `web_admins.role` column already exists for this when wanted.

## New: admin email broadcasts, segmented by event/tag

**Why:** requested — admin wants to build a segment from customers who
actually purchased (filtered by event, or by an event's tag/category)
and send them an email. SMS is planned as a second channel later, which
shaped the design (schema and API both carry `channel` from day one
instead of assuming email-only).

- **New website admin page, `admin/broadcast.html`** (+ sidebar link on
  all seven admin pages): checklist of events and of every tag currently
  in use (derived from real event data, not a fixed vocabulary — tags
  are free-text per event throughout this codebase), a live "matched /
  emailable" count as filters change, a subject+body compose box, and a
  history table of past sends with per-broadcast sent/failed counts.
  Event and tag filters combine as OR (either one matching an event
  includes its customers) — two different ways to point at the same kind
  of audience, not two conditions that must both hold. No filters at all
  = every customer who has ever completed a purchase.
- **Audience = distinct customers with at least one `approved`
  reservation** matching the filter — an actual completed purchase, not
  an abandoned or still-pending one.
- **Async by design**: creating a broadcast resolves the audience
  immediately (so the admin sees a real count back, not a promise) and
  queues one row per emailable customer; a new background loop
  (`run_broadcast_loop_sync`, same shape as the existing sync expiry/
  backup loops) drains it a few at a time over SMTP, so sending to a
  real-sized list can't block the admin's HTTP request. A customer with
  no email on file is counted in "matched" but not queued — there's
  nowhere to send this version of a broadcast to them yet.
- New tables `broadcasts` / `broadcast_recipients` (schema v14, additive)
  — per-recipient rows (not just an aggregate count) so a failure is
  attributable, same reasoning as keeping individual `payments` rows
  instead of a running total on `reservations`.
- **Caught mid-build**: `services/broadcast_service.py` already existed
  — a working, pre-existing Telegram-side broadcast feature (admin picks
  an audience of Telegram users inside the bot itself and messages them
  directly; see `handlers/admin_panel.py`'s `broadcast_*` handlers) that
  a first pass at this work overwrote outright without reading the file
  first. Caught before deploy by `git status` showing the file as
  modified rather than new, which shouldn't have been possible for a
  file this session had never touched before. Fixed by restoring the
  original Telegram functions and adding this feature's functions
  alongside them under `email_`-prefixed names, so nothing about the
  existing in-bot broadcast flow changed — re-verified both the Telegram
  handler's imports and the new website flow end-to-end afterward.
- **Verified** through the real admin UI: filtering by an event's tag
  showed the right matched/emailable split (including a customer with a
  purchase but no email on file, correctly matched-but-not-queued);
  sending queued the right recipients; the background loop picked them
  up and the history table's status moved from "در حال ارسال" to
  "انجام‌شده" with the correct sent count; the actual email content
  (subject/body) came through unchanged in the delivery log.

## Fixed: mobile nav menu collapsed into a sliver, bled over the page

**Why:** reported with a real phone screenshot on `account.html` —
opening the mobile hamburger menu showed nav links scattered over the
page content with no solid background behind them, overlapping the
page's own text, instead of a normal full-screen menu.

- **Root cause, confirmed by direct measurement (not guessed)**: the
  mobile nav overlay is `.nav-links{position:fixed;inset:0}` — meant to
  cover the whole viewport. Its ancestor `.site-header` has
  `backdrop-filter:blur(22px)`, and `backdrop-filter` (like `filter` and
  `transform`) makes an element a *containing block* for any
  `position:fixed` descendant. So `inset:0` was resolving against
  `.site-header`'s own ~52px-tall box, not the viewport — squeezing the
  full-screen menu into that sliver; its flex children then visually
  overflowed that box (no `overflow:hidden` on it) and rendered on top
  of the page underneath, with no real backdrop behind them, exactly
  matching the screenshot.
- **Fix**: `.site-header:has(.nav-links.open){backdrop-filter:none}` —
  drops the header's backdrop-filter only while the mobile menu is open,
  removing the containing block so `.nav-links` covers the actual
  viewport again. CSS-only; `.nav-links.open` was already the existing
  toggle's single source of truth for "menu is open," so no JS change
  needed.
- **Verified** with Playwright: measured `.nav-links`' rendered height
  go from 52px (bug) to the full 844px viewport height (fixed) the
  moment the CSS rule was added; confirmed the header's backdrop-filter
  correctly restores on close; reproduced the exact scenario from the
  report (account.html, scrolled, menu open) and confirmed a clean
  full-screen menu; confirmed desktop's `.nav-links` (`position:static`,
  inline flex row) is completely untouched — the rule only ever applies
  inside the same 768px mobile media query the broken behavior lived in.

## Homepage: active events moved up, founder bio card removed

**Why:** get a visitor to what's actually on right now faster, without
scrolling past the founder bio card first.

- Removed the founder bio card section from the homepage entirely (it
  still lives on its own page, `about-mansour.html`, reachable from nav/
  the paths grid — nothing about it was deleted, just moved off the
  homepage).
- The "همین حالا در خانه ماورا" (active events) slider — previously
  below the paths grid — now sits in that exact spot instead: right
  after the hero and quote ribbon, before anything else.
- `initBio()` (the homepage bio card's read-more toggle) removed as dead
  code along with it — confirmed `about-mansour.html`'s own bio
  read-more (different ids, its own inline script) is entirely
  independent and unaffected.
- Verified with Playwright: bio card gone from the DOM, section order is
  hero → quote → active-events slider → paths → upcoming events →
  gallery, and the slider still renders real event cards correctly in
  its new position.

## Waiting-list approval: two real bugs from live use, fixed

**Why:** using the page just shipped, both surfaced immediately —
approving a *website* waiting-list entry showed up in the reservations
list tagged "تلگرام", and approving created a still-unpaid reservation
with no ticket, no way to finalize it from the page at all.

- **Bug 1 — wrong source, root cause**: `increase_capacity_and_reserve_
  locked()` (the one atomic operation both the Telegram overflow-approval
  flow and the new website one call) hardcoded `source='telegram'` in
  its INSERT — literally the only value it had ever needed, until a
  second call site (this feature) needed it to vary. `waiting_list`
  itself never recorded which channel a request came from either, so
  there was nothing to pass through even after fixing that. Fixed at the
  root: schema v13 adds `waiting_list.source` (defaults existing rows to
  'telegram' — true for everything that could predate this column, since
  the website waiting-list flow is this session's own recent feature);
  both places a waiting-list entry gets created now record their real
  source ('website', 'telegram', or 'phone' for the manual/walk-in
  path); `increase_capacity_and_reserve_locked()` and
  `approve_waitlist_entry()` now pass that real value through instead of
  a hardcoded literal.
- **Bug 2 — no way to finalize, redesigned**: `approve_waitlist_entry()`
  used to mirror the Telegram-only flow exactly — grow capacity, create
  a `pending_payment` reservation, and wait for the buyer to send a
  receipt over Telegram. That makes sense when the buyer is the one who
  acts next; it doesn't when an admin on the website is the one deciding
  to seat this person. Redesigned to finalize on the spot: the approval
  modal now has an editable price field (pre-filled with the event's own
  effective price, editable for a discount/cash-already-collected/
  different-headcount case), and confirming creates the reservation
  already `approved` with that price and issues a real ticket/QR
  immediately — same as `create_manual_reservation()`'s existing phone/
  walk-in booking path, just reached from this page instead of a staff
  phone call.
- **Verified** end-to-end through the real admin UI: a website-sourced
  entry now shows "سایت" (not "تلگرام") in the list; approving it with
  an admin-edited price (450,000 → 300,000) produced, confirmed via
  direct DB read, a reservation with `status='approved'`,
  `source='website'`, `unit_price=300000` (the edited amount, not the
  suggested default), and a real `reservation_code`; the confirmation
  email matched the normal approve-reservation template exactly, ticket
  code included.

## Waiting-list admin: a new website admin page, and a real gap it closes

**Why:** asked "where can I see waiting-list reservations in admin?" —
the honest answer was nowhere. A full session's waiting-list entry has
never gone into the `reservations` table at all (a separate
`waiting_list` table always held it), so the website admin's
reservations page — which only ever reads `reservations` — could never
show them. The only existing management path was Telegram-only: an
inline "approve/reject" prompt sent to admins with the right permission,
which messages the buyer back over Telegram. A website-originated
waiting-list signup (this session's own earlier feature) triggered none
of that — no Telegram prompt, no email, nothing — the request was
created and then effectively invisible to every admin.

- **New `website/pages/admin/waitlist.html`** (+ sidebar link on all six
  existing admin pages): every pending waiting-list entry, across every
  event/session, with buyer name/phone/email, event/session, and
  Approve/Reject actions. Approve grows that session's capacity by one
  and creates a real `pending_payment` reservation for the buyer — same
  atomic `approve_overflow_atomic()` operation the Telegram flow already
  used.
- **New backend**: `waitlist_repo.list_all()`, `reservation_service.
  list_pending_waitlist()/approve_waitlist_entry()/reject_waitlist_entry()`,
  and `GET/POST /api/v1/admin/waitlist...` endpoints (mirroring the
  existing reservation admin endpoints' auth/response shape). No schema
  change — `waiting_list` already had everything needed.
- **Notification is email-first**, not Telegram-first like the existing
  flow: a website waiting-list buyer may have no Telegram account at all
  (identity resolves by email). They always get an email on approve/
  reject; if they *do* have a linked Telegram account, a best-effort
  message is also queued via `bot_outbox` — though unlike the Telegram-
  native flow, this can't arm the buyer's bot FSM to auto-attach their
  next photo as a receipt (that requires the bot process's own in-memory
  state, unreachable from a separate API process) — the message just
  tells them what to do next.
- **Real pricing bug fixed in the same function this reuses**:
  `approve_overflow_atomic()` always priced the new seat at the global
  default ticket price, ignoring any per-event custom price — predates
  per-event pricing and was never updated for it. Now uses the session's
  own event's effective price, benefiting the existing Telegram overflow-
  approval flow too, not just this new one.
- **Verified** end-to-end: seeded real waiting-list entries (including
  one behind a session actually at capacity), logged in as admin,
  approved one (confirmed via direct DB read: waiting_list status
  'converted', a real `pending_payment` reservation created at the
  correct per-event price, session capacity incremented by the right
  amount, and the plain-text approval email printed to the log with
  correct content) and rejected another (status 'rejected', rejection
  email printed) — all through the real admin UI, not by calling the
  service functions directly.

## Waiting-list signup moved into the booking modal

**Why:** joining the waiting list for a sold-out session was three
stacked native `prompt()` dialogs, entirely outside the booking modal —
a different, lower-quality flow for what's functionally a very similar
action.

- `joinWaitlist()` (three `prompt()` calls) replaced by
  `selectWaitlistSession()`, which reuses the exact same modal and the
  same picker → form → confirm → loading → result steps as a normal
  booking — a new `__bk.mode` ('book' | 'waitlist') flag is the only
  branch point. In waitlist mode: no quantity stepper, no payment/receipt
  section (there's no confirmed seat to pay for), the summary card
  explains what's happening ("این سانس تکمیل ظرفیت است؛ با ثبت‌نام در
  لیست انتظار...") instead of showing a price breakdown, and the confirm
  screen's title and button read "ثبت‌نام در لیست انتظار" instead of
  "ثبت رزرو". The full-session check in the form step is skipped for
  this mode specifically, since a full session is the very reason this
  flow exists.
- `confirmAndSubmit()` needed no branching at all beyond that — it already
  called the one endpoint that lets the backend itself decide
  waiting-vs-booked from real capacity, so the same submit path serves
  both modes unchanged.
- Verified with Playwright: no native `prompt()` fires anymore, the
  waitlist button switches straight into the modal's form step with
  quantity/payment correctly hidden, the confirm screen shows the right
  title/button text and no receipt line, and the final result is the
  waiting-list success message. A full normal-booking run (multi-date,
  back navigation, edit, receipt upload) confirmed nothing regressed on
  the shared code paths.

## Event page: Telegram/phone demoted to a support line, not a booking CTA

**Why:** with real in-page booking live, showing "Book on Telegram" and
a phone-call button right next to the actual booking button suggested
they were equally valid ways to book — they aren't anymore; they're for
questions.

- Removed the `directContact` buttons from next to the booking CTA.
- Added a plain-text line further down the page (between the info/
  booking grid and the feedback box), only when the event has a
  Telegram and/or phone contact set: "در صورتی که سوال یا نیاز به
  پشتیبانی دارید، از طریق اکانت تلگرام خانه ماورا یا شماره موبایل ...
  با ما در ارتباط باشید." — small muted text, not a button, with the
  Telegram account and phone number as inline links (Telegram opens in
  a new tab). Omitted entirely when an event has neither set.
- Verified with Playwright: no Telegram/phone links remain inside the
  booking area, the support line reads exactly as specified with both
  contacts wired to the right hrefs, and it's correctly absent for an
  event with no contact info at all.

## Booking form: staged flow (picker → form → confirm → result)

**Why:** direct feedback on the just-shipped modal — the date/session
picker stayed on screen underneath the buyer-info fields once a session
was picked, growing the form instead of focusing it; and pressing
"ثبت رزرو" booked immediately with no chance to review what was about to
be sent, then left the whole (now-disabled) form sitting on screen next
to the result.

- **Picking a session now switches the view**, it doesn't just reveal
  more of it: the date chips + session list (`bkPickerBlock`) hide, and
  only the form (name/phone/email + payment) shows. A "بازگشت" button
  brings the picker back on demand — nothing about the date is shown
  while filling out the form, only when the buyer explicitly asks to
  change it.
- **The form's button no longer books anything.** It validates (same
  checks as before: sold-out race, file type/size) and moves to a
  read-only recap of exactly what's about to be sent — event, date,
  session, quantity, total, name, phone, email, and the receipt's
  filename (or "بدون رسید پرداخت" if none was attached). A "ویرایش" link
  goes back to the form with everything still filled in.
- **Only the recap's own button calls the API** — reservation, then
  receipt upload if one was attached — behind a spinner + "در حال ثبت
  رزرو…". When it resolves, `bookingWidget`'s entire contents are
  replaced with just the outcome message; the form/picker/confirm markup
  is gone, not hidden, so there's nothing left over to scroll past.
- **Verified** with Playwright: session pick hides the picker and shows
  only the form; back returns to the picker (date chips included) with
  the form hidden; picking a different date/session and continuing shows
  a confirm screen with the actual typed values and receipt filename;
  edit returns to the form with values intact; confirming shows the
  loading spinner then replaces everything with only the result message;
  a rejected file type on "ادامه" correctly stays on the form instead of
  advancing. No console errors in any of it.

## Booking form: one step, modal/bottom-sheet, and rewritten messages

**Why:** direct feedback on the live booking widget — it was two forms
pretending to be one flow (buyer info, then a second reveal for the
payment receipt), it sat as plain page content with no visual separation
from the rest of the event page, and several of its messages were
unclear or, in one case, outright wrong.

- **Merged into one form.** `submitBooking()`/`showPayment()`/
  `uploadReceiptUI()` used to be three separate functions across two
  visible steps — creating the reservation, then revealing a second panel
  for the payment receipt. It's now a single `<form>`: buyer info and the
  (optional) receipt upload are shown together, and one submit does both
  API calls in sequence (create reservation, then upload the receipt if
  one was attached) before showing one combined result. Once the
  reservation succeeds the whole form locks (`__bk.submitted` latch) so a
  stray double-click or a receipt-upload failure can never fire a second
  reservation for the same booking attempt.
- **New `.bk-modal`/`.bk-modal-overlay` component**: centered dialog on
  desktop, bottom sheet (slides up, rounded top corners, grab handle) on
  mobile at the site's existing 760px breakpoint. The booking widget used
  to render inline into the event page itself; it's now opened from a
  "رزرو بلیت" button and closes via the ✕, the overlay backdrop, or Esc.
- **Real bug fixed**: the file-type validation for the payment receipt
  showed `bk_sel_date` ("ابتدا یک روز اجرا انتخاب کن" — pick a date
  first) on a non-image file — copy for a completely unrelated step,
  left over from a shared string. It now has its own message
  (`bk_file_type_error`).
- **Message rewrite across the flow**: the missing-fields alert used to
  slash-join three field labels (`نام / موبایل / ایمیل`) with no
  sentence around them — replaced by relying on the browser's own
  required-field validation (the three inputs already had `required`)
  instead of a custom alert. Native `alert()`/`prompt()` popups for
  submit-time errors (sold-out race, network failure) are now inline
  banners inside the modal instead — jarring next to a custom dialog, and
  blocking. The one generic "pick a date" string previously reused for
  three different situations (no sessions on the event at all, no
  sessions on this specific date, and the file-type bug above) is now
  three separate, situation-specific messages. Success copy now reflects
  what actually happened: whether the receipt was attached and accepted,
  skipped (with a clear next step — send it via Telegram), or attempted
  but failed to upload (the reservation itself still stands either way —
  the copy says so explicitly, so the buyer doesn't think they need to
  start over).
- **Small structural fix while touching this code**: the sold-out
  session's "join waiting list" button used to sit *inside* a disabled
  `<button class="bk-session">` — a `<button>` cannot contain another
  `<button>`, which browsers silently restructure to cope with. Session
  rows are now `<div>`s (`role="button"`/`tabindex`/Enter-Space handling
  on the selectable ones), so the waiting-list button nests cleanly.
- **Verified** with Playwright at both a desktop viewport (centered
  modal) and a mobile viewport (bottom sheet): a single-date event (date
  picker skipped, as before), a multi-date event (chips shown, first
  auto-selected), a sold-out session's waitlist button, the corrected
  file-type error message, a full submit with a receipt attached, a full
  submit with the receipt skipped, and a forced double-submit call
  confirmed as a no-op after the first succeeds — no console errors, no
  failed requests, in every scenario.

## Reservation migration — phase 4 (admin reservation panel, on the website)

**Why:** the last piece — an admin no longer needs Telegram to run the
reservation side of the business. Session management, the approval
queue (with receipt viewing), and door check-in all live on the website
now, next to the content admin they already use.

- **Finding #8, actually fixed**: `POST /admin/reservations/<id>/approve`
  `/reject` and `/bulk-approve` recorded `reviewed_by=0` for every
  website-side decision — with one admin that's invisible, but it means
  `payments.reviewed_by` can never say which admin approved what once a
  second admin has access, which is exactly the moment it matters. All
  three now pull the real `admin_id` from the JWT payload. Verified two
  different admin accounts approving/rejecting different reservations
  and reading `payments.reviewed_by` back from the database — 1 and 2,
  not 0 and 0.
- **New `website/pages/admin/reservations.html`**: the approval queue —
  search/filter, bulk-approve, CSV export, and (new) an actual receipt
  viewer. Restored from before the split with the receipt viewer added,
  since the old page never had one — it just printed "ارسال شده" as
  plain text, with no way to see what was actually submitted.
- **Session management folded into `admin/events.html`**'s own edit
  form** (add/close/delete a session, right where an admin is already
  looking at the event) rather than a separate calendar page — matches
  how the reservation-migration plan scoped this phase.
- **New `website/pages/admin/checkin.html`**: door ticket verification/
  check-in, restored from before the split. **Found and fixed a real bug
  in the restored code while testing it with a genuine signed payload**
  (not just an invalid one): the confirm button was wired via
  `onclick="doCheckin(${JSON.stringify(payload)})"` — `JSON.stringify`
  wraps a string in double quotes, which prematurely closed the
  `onclick="..."` HTML attribute (also double-quoted) the moment a real
  signed payload was clicked, throwing "Unexpected end of input" and
  silently doing nothing. Never caught before because nothing had
  exercised it with a real payload through the actual UI. Fixed by
  binding the handler with `addEventListener` and a closure instead of
  an inline attribute — the shape every other action on this page (and
  the reservation queue) already used, which is why only this one spot
  had the bug.
- **A second real bug, also only caught by testing across two real
  browser ports**: `GET /admin/reservations/<id>/receipt` (the private
  receipt endpoint from phase 0) never set `Access-Control-Allow-Origin`
  — every JSON response gets it for free from `_send_json()`, but this
  is a raw byte response that has to set headers itself, same as
  `ticket.pdf` already did. Fixed to match.
- `API.sessions` gained admin methods (`refreshAdmin`/`create`/
  `setStatus`/`delete`), `API.reservations` gained `bulkApprove`/
  `viewReceipt`, `API.tickets` (verify/checkin) is back — all restored
  from before the split, receipts additionally routed through an
  authenticated `fetch()` → blob (same reasoning as phase 3's ticket
  download — a plain link can't carry a Bearer token).
- Verified end to end with a live server + Playwright working the actual
  UI: added a session from the events admin form and watched it appear
  correctly Jalali-formatted; two reservations approved/rejected by two
  different logged-in admins with receipts viewed in between; a real
  signed ticket looked up and checked in, confirmed both by the UI
  message and a re-lookup showing "قبلاً وارد شده". Zero console errors
  once both bugs above were fixed.

## Reservation migration — phase 3 (booking, live on the website)

**Why:** the whole point of this migration — a customer can now book an
event directly on mavarahome.com, no Telegram required, and the
reservation lands in the exact same database, visible to the same admin
tools, the same instant. Journeys 2 and 4 from the original request.

- **`GET /api/v1/reservations`** (website booking) now requires `email`,
  not just phone — not optional, on purpose: login is email-only
  (customer_auth_service), so a booking made without one would have no
  way back to it later. `reservation_service.start_reservation_web()`
  now goes through `get_or_create_customer()` (phase 0) with phone AND
  email together, which is what actually closes the "reservation archive
  is empty" finding — the account is matched/created at booking time,
  not left for a login attempt to somehow resolve to the same row later.
- **`_session_public()` gained `date_display`** — a pre-formatted Persian
  Jalali (or Gregorian, per the event's `calendar_type`) date string,
  computed server-side via the already-tested `utils/jalali.
  display_date_for_event()`. This is what let the booking widget group
  sessions into date cards without resurrecting `jalali-calendar.js` (a
  whole client-side calendar-conversion library, deleted as unused in the
  split) just to duplicate logic the backend already had correct.
- **`website/assets/js/site.js`**: restored the step-by-step booking
  widget on `event-detail.html` (date → session → quantity → buyer info →
  payment → receipt upload) from before the split, adapted to collect
  email alongside name/phone, and to the current design system. The
  event's own Telegram/phone contact buttons stay underneath as a
  fallback — an event with no sessions yet, or one an admin still prefers
  to handle personally, both keep working exactly as before. All the
  `.bk-*` CSS this needed was already sitting unused in `styles.css`
  (the split only ever removed the JS/HTML) — found by checking before
  writing any new CSS.
- **New `website/pages/account.html`**: email-OTP login, reservation
  archive, ticket PDF download. Restored from before the split with two
  real fixes, not just a copy: (1) the old ticket-download was a plain
  `<a href>` to an endpoint that requires a `Bearer` token — a link can't
  set that header, so it always 401'd; now an authenticated `fetch()` →
  blob → triggered download. (2) dropped the buyer-support messaging
  section entirely — out of this migration's scope (journeys 1-4 only),
  and it doesn't work stand-alone without also restoring
  `admin/messages.html`, which nothing here asked for.
- Nav gained a "حساب من" (My Account) link; `nav_account` and the
  `bk_*`/`pay_*`/`reserve_*` i18n keys (both languages) — all pruned in
  the split — are back.
- Verified with a live server + Playwright driving the actual UI, not
  just API calls: picked a date and session, filled buyer info, submitted
  a real reservation, uploaded a receipt image, approved it as admin,
  logged into the account page with the real OTP read live off the
  server's log (SMTP unset in this sandbox), and downloaded the resulting
  ticket — confirmed as a genuine single-page PDF, not just a 200
  response. Zero console errors, zero failed/4xx/5xx requests throughout;
  a homepage/events/team regression pass afterward came back clean too.

## Reservation migration — phase 2 (schema v11 → v12)

**Why:** phase 3 (booking UI on the website) needs a customer identity
that works the same regardless of which channel someone books through —
phase 0 built the merge logic (`get_or_create_customer()`), phase 2 is
what actually uses it for something a customer notices: picking a login
method, and finding out what happened to a reservation without having to
go check Telegram.

- **Admin-configurable login channels.** New setting
  `otp_channels_enabled` (comma-separated — deliberately not JSON, since
  it's edited as free text from the Telegram settings menu, where a
  syntax typo must degrade safely instead of locking out every customer;
  `settings_service.get_otp_channels_enabled()` drops anything it doesn't
  recognize and always falls back to `["email"]`). New public
  `GET /api/v1/otp-channels` so a login page can build its channel picker
  from this instead of hardcoding "email". `customer_otp` gained a
  `channel` column (metadata; the actual lookup is still by the `email`
  column, since email is the only channel with a real send path).
- **Phone login is infrastructure-only, not implemented** — matches the
  explicit decision to prepare the schema/settings for it without
  building a non-functional feature: `channel="phone"` is accepted
  end-to-end (settings, API, service) and always returns
  `channel_not_supported`, checked BEFORE the enabled-channels list so
  enabling it in settings can never look like it would work when it
  can't. Wiring in a real SMS provider later only means implementing one
  branch in `customer_auth_service.request_otp()`.
- **`/api/v1/auth/customer/request-otp` and `/verify-otp`** now take
  `{"identifier", "channel"}` (channel defaults to `"email"`); the old
  `{"email": ...}` shape still works unchanged.
- **Dual-channel reservation notifications** (the "website customer never
  finds out their reservation was approved/rejected" finding from the
  product review — the only delivery channel, `bot_outbox`, is keyed by
  `telegram_id`, which a website-only customer doesn't have).
  `services/reservation_service.py`'s `approve_reservation()`,
  `finalize_rejection_if()` and `reject_reservation()` now email the
  customer (event title, Jalali-formatted session date, reservation code
  or rejection reason) whenever they have an email on file — regardless
  of which channel (Telegram or the future website flow) triggered the
  approval/rejection, so this can't drift out of sync with either one.
  No-op, not an error, for a Telegram-only customer with no email (they
  already got a Telegram message from the handler that called into this
  service) or a send failure (best-effort — `send_email()` never raises,
  so this can never fail a status transition that already committed).
  `database/repositories/users.py` gained `get_by_id()`, a genuinely
  missing basic lookup this needed.
- Two new tests in `bot/test_bot.py`; verified again through the real
  HTTP admin-approve endpoint (not just the service layer) — captured the
  printed fallback email (no SMTP configured) and confirmed it named the
  actual event, date and reservation code, not placeholders.

## Reservation migration — phase 0 + phase 1 (schema v9 → v11)

**Why:** a product review ("critically review the reservation journey and
prepare a migration plan") found the split below had, in the meantime,
left three real security gaps and re-introduced a two-source-of-truth
content problem, on top of the original goal (bring booking onto the
website itself, still reachable from Telegram too) needing a shared
backend the split had deliberately removed. Full findings and the
5-phase plan are in the product-review doc shared with the client;
phases 0 and 1 are done, phases 2-4 (customer identity UX, booking UI,
admin reservation panel on the website) are still ahead.

**Phase 0 — closed the three critical findings**, verified against a live
server (curl), not just the test suite:
- Removed `GET /api/v1/reservations?phone=...` (`bot/api/server.py`) — it
  returned anyone's full reservation history to any caller who knew or
  guessed a phone number, no auth at all, and created a user row as a
  side effect of a GET. The authenticated replacement customers already
  have is `GET /api/v1/account/reservations` (JWT).
- Payment receipts moved out of `media/` (served to anyone, and directly
  by Nginx in production) into a new `private_media/` tree. New
  `GET /api/v1/admin/reservations/<id>/receipt` serves it, admin-only.
  Two receipt images already committed at the old public path (test data)
  were removed from git; `private_media/` added to `.gitignore`.
- `database/repositories/users.py`: three near-identical
  get-or-create-user functions (each with a subtly different `WHERE`
  clause — the actual bug: one filtered `AND telegram_id IS NULL`, so a
  phone number belonging to someone who'd separately used the bot got a
  duplicate row on every manual booking) collapsed into one
  `get_or_create_customer()`. Email takes priority over phone (product
  decision); an existing row found by either identifier gets backfilled
  with whichever field the caller newly supplied, never overwriting a
  field that's already non-empty — this is also the fix for "a
  reservation made by phone, then logged into later by email, showed an
  empty archive" (the two used to resolve to two different rows). Backed
  by real partial-`UNIQUE` indexes on `users.phone` and `users.email` now
  (`WHERE ... IS NOT NULL AND != ''`, so the many legitimately-blank rows
  never collide). Three new tests in `bot/test_bot.py` cover this.

**Phase 1 — reunified the backend, since the reason to split it away is
gone.** `website/backend_cms/` (a standalone content-only Flask CMS,
built when this site needed to run on shared hosting with no SSH) is
retired now that a real VPS with SSH exists. `website/` connects directly
to the same unified API the bot uses again — one database, one source of
truth for events/portfolio/team, immediately available to both channels.
- Schema v11: `events` gained `date` (free-text showtime), `status`
  (`ongoing`/`upcoming`/`archived` — the website's display lifecycle) and
  `tags` (JSON array) — the three columns `backend_cms`'s own `events`
  table had that bot's never did. `status` also drives `is_active` (what
  the bot's booking flow actually checks) unless a caller passes
  `is_active` explicitly in the same request — see
  `events_repo.update_event_fields()`'s docstring for why the two can't
  be allowed to silently drift apart.
- `bot/api/server.py`: `_event_public()` now returns `date`/`status`/
  `tags`; admin event create/update accept them (`tags`, like `gallery`,
  json-encoded before storage). Fixed the admin `PATCH /admin/events/<id>`
  handler's `is_active` handling while touching this code anyway — it
  used to run as a *separate* `set_event_active()` call before
  `update_event_fields()`, which raced with the new status→is_active
  derivation when both were in the same request body; both now flow
  through `update_event_fields()` together. Also added the missing
  `"team"` entry to `/admin/upload`'s `kind` whitelist — team-photo
  uploads were silently landing in `media/gallery/` instead of
  `media/team/` (worked, just confusing on disk).
- `website/assets/js/site.js`'s `pp()` path helper never had a case for
  `media/...`-prefixed paths (what the upload endpoint actually returns)
  — fine from the site root, but resolved against the wrong base from any
  `/pages/*.html` page (event detail, team, portfolio — most image
  displays), silently swapped for a fallback icon by every image's
  `onerror` handler instead of surfacing as an error. Fixed.
- `bot/utils/scheduler.py`: the expiry loop that frees a `pending_payment`
  reservation's seat, and the daily DB backup, only ever ran inside
  `bot.py`'s asyncio loop — if the API is deployed without the Telegram
  bot process running (the exact situation this project was in), neither
  ran at all: a session would look increasingly "full" without actually
  being full, and the database was never backed up. New
  `run_expiry_loop_sync()`/`run_backup_loop_sync()` run as plain daemon
  threads inside `api/server.py` itself (started from `main()`), so both
  work regardless of whether `bot.py` is up. Deliberately not a port of
  the full async `run_expiry_loop` — that one also does Telegram-only
  chores (card-rotation reminders, review nudges, owner-removal
  finalization) that genuinely need `bot`; only the correctness-critical
  part (freeing the seat) needed a bot-independent path.
- Verified with a live server + Playwright walkthrough (homepage, events
  listing, event detail, admin login, admin events list) against the
  reunified API — zero console errors, zero failed/4xx/5xx requests,
  `status`/`tags`/`date` round-tripping correctly end to end.

## Follow-up: split website/ from bot/ so the site can host on plain shared hosting (no SSH)

> **Superseded by the reservation-migration phase 1 above** —
> `website/backend_cms/` described in this section no longer exists.
> Left in place for history; do not follow its deployment instructions.

**Why:** `website/` previously had no backend of its own — every admin
action (events, portfolio, team) went through `bot/api/server.py`, the
same unified process the Telegram bot's whole reservation platform runs
on. That process needs a persistent background service (systemd) and a
real server with SSH — exactly what an ordinary shared-hosting cPanel/
DirectAdmin plan (Python App / Passenger, no SSH) can't run. Per an
explicit request to make `website/` hostable on that kind of plan, with
reservation staying entirely the bot's job: `website/` is now fully
independent of `bot/` — different backend, different database, no
shared code, deployable separately (and, going forward, on completely
different hosting if wanted — see the earlier discussion this
implements).

**New: `website/backend_cms/`** — a small, synchronous Flask (WSGI) app
that manages ONLY public content: events (display fields — no sessions/
capacity/price), portfolio, team members, and its own admin login. Its
own SQLite database (`data/content.db`), nothing shared with `bot/`.
- `auth.py` — the same stdlib-only PBKDF2 + HS256 JWT approach as
  `bot/utils/auth.py` (independent copy, not an import — this backend
  has zero dependency on `bot/`).
- `app.py` — all routes registered on a Blueprint at BOTH `/v1/...` and
  `/api/v1/...` (see the comment above `api = Blueprint(...)`): whether
  a cPanel/DirectAdmin "Application URL" mount point strips its own
  prefix from the path the WSGI app sees is genuinely inconsistent
  across panel/Passenger versions — registering both removes the
  guesswork instead of gambling on one behavior at deploy time.
- Login has the same in-memory sliding-window rate limit
  (`bot/api/server.py`'s pattern) — 8 attempts / 15 minutes per IP+username.
- `MEDIA_ROOT` (env var, defaults to a sibling `website/media/`) is
  where uploads land — deliberately a plain folder the real webserver
  serves directly as static files, not proxied through the Python app
  (shared hosting's static file serving is faster and simpler than
  routing binary downloads through Passenger).
- `passenger_wsgi.py` — the exact entrypoint cPanel/DirectAdmin's
  Passenger-based Python App feature expects.
- `create_admin.py` — CLI bootstrap for the first admin account, run
  from the panel's own virtual-environment terminal (no SSH needed).
- `DEPLOYMENT.md` — click-by-click cPanel/DirectAdmin instructions.

**Booking moved fully to Telegram — no reservation UI on the website at
all anymore.** `pages/event-detail.html`'s booking widget (the whole
step-by-step date → session → qty → buyer info → payment → receipt-
upload flow, ~190 lines of `site.js`) is gone. In its place: a "book via
Telegram/phone" button built from the event's own `contact_phone`/
`contact_telegram` fields — the same link-based booking the original
site (`actor-portfolio/`) always used, before the reservation platform
existed. Removed pages (all reservation/ticket/customer-account
surfaces, all bot-domain now): `pages/account.html` (customer login
dashboard), `pages/connect-telegram.html` (deleted — it existed only to
support that same account login's Telegram-linking step, which no
longer exists on the website side), `pages/admin/reservations.html`,
`checkin.html`, `messages.html`, `ticket-template.html`,
`admin/calendar.html` (session/capacity management). `assets/js/
jalali-calendar.js` and `legacy-data.js` are now fully unused (nothing
left references them) and deleted rather than left as dead code.

**Also fixed while rebuilding `site.js`'s event rendering against the
new backend's actual field names** (several were stale — leftover
assumptions from before Phase 1's backend unification that had never
been reconciled, found while doing this pass): `coverHTML()` read
`e.images[0]`, a field that never existed on any real backend response —
now reads `e.poster`/`e.gallery[0]`, matching what the admin form
actually uploads. The homepage's "ongoing/upcoming" filter checked for
`e.status === 'active'`, a status value nothing ever sets — now checks
`'ongoing'`/`'upcoming'`, matching `badgeHTML()`'s own three-state
convention. `pages/admin/events.html`'s date field (`evDate`) was
rendered in the form but never actually included in the save payload —
now wired through as a plain free-text field (`date`), and a `tags`
input was added (comma-separated) since `site.js`'s tag-chip filter bar
already expected an `event.tags` array that no admin form ever
populated.

**`bot/` is completely untouched by this pass** — same reservation
platform, same database, ready to be hosted (on its own, real,
SSH-capable host) whenever wanted; see `bot/README.md`.

**Verified**: the full stack running together locally (`backend_cms`'s
Flask dev server + a plain static file server for `website/`, two
separate processes/ports, exactly mirroring the real split-hosting
setup) — admin login (including the rate limiter actually triggering at
attempt 9 and blocking even the correct password until the window
expires), create/edit/delete for events/team/portfolio, image upload,
and the Blueprint's dual `/v1/` + `/api/v1/` registration both
resolving. Screenshotted (Playwright): homepage, events listing (tag
filter), event detail (the new Telegram/phone booking buttons, no
session table), team page, admin dashboard, admin events list, and the
edit-event modal with real data (title/status/location/tags) populated
from the new backend — zero console errors on any page. Every changed
Python file `py_compile`s clean; `app.js` and `site.js` `node --check`
clean.

## Follow-up: customer login rewritten from phone+Telegram to email OTP (schema v8 → v9)

The original Phase 4 design used phone number + OTP delivered through the
Telegram bot, because this project has no SMS provider — a website-only
customer (no telegram_id yet) had to open a one-time deep link into the
bot before they could receive codes at all. Per a later request, this
whole flow is rewritten to plain email OTP, which needs no such linking
step.

**Schema v9** (additive): `users.email` and `customer_otp.email` columns
(indexes created *after* the ALTER-column loop in `init_db()`, not inside
the earlier `SCHEMA_STATEMENTS` list — indexing a column before it exists
silently no-ops via the existing try/except-and-log-a-warning guard,
which is how a first version of this migration was caught: a fresh DB
logged "Skipped schema statement (no such column: email)" for both new
indexes until they were moved). `customer_otp.phone` stays `NOT NULL` for
backward compatibility with existing rows; new email-based rows just
write `''` into it rather than requiring a full SQLite table rebuild to
relax that constraint.

**`utils/email_sender.py`** (new) — real SMTP sending via stdlib
`smtplib`, configured through `.env` (`SMTP_HOST`/`PORT`/`USER`/`PASS`/
`FROM`/`FROM_NAME`/`USE_TLS`, see `config/settings.py`). If `SMTP_HOST`
is empty, prints the email to console/log instead of sending — same
"works locally without real credentials" fallback already used for
`BOT_TOKEN`.

**`database/repositories/customer_auth.py`** (rewritten) — `create_otp`/
`verify_otp` now key on `email` instead of `phone`; `create_link_token`/
`consume_link_token` (the Telegram deep-link tokens) are removed — the
`telegram_link_tokens` table itself is left in the schema, just unused.

**`services/customer_auth_service.py`** (rewritten) — `request_otp(email)`
validates the address, creates the user row if needed
(`users_repo.get_or_create_user_by_email`), generates a code, and emails
it directly — no "channel": "telegram"/"link_required" branching left,
since email never needs a linking step. `link_telegram_from_token` is
gone.

**`database/repositories/users.py`** — new `get_or_create_user_by_email`
and `set_email(user_id, email)` (lets an existing phone-based guest
booking be attached to an email for later login — used by the reworked
seed data below; not yet exposed as a user-facing "add email to your
booking" flow, which would be a reasonable next step if wanted).

**`api/server.py`** — `POST /api/v1/auth/customer/request-otp` and
`/verify-otp` now take `{"email": ...}` instead of `{"phone": ...}`;
`verify-otp`'s response carries `"email"` instead of `"phone"`.

**`handlers/common.py`** — the bot's `/start` handler no longer parses a
`LINK-<token>` payload (dead code now that login needs no Telegram
linking); the rest of `/start` — welcome message, admin/staff menus — is
untouched.

**Website** — `pages/account.html`: login step is now a single email
input → OTP input (no more "connect Telegram" branch/screen).
`assets/js/app.js`'s `API.customerAuth` renamed its phone-keyed
functions/storage to email (`requestOtp(email)`, `verifyOtp(email, code)`,
`getEmail()`, `sessionStorage` key `mh_cust_email`).
`pages/connect-telegram.html` no longer handles a `?link=` query param
(the account-linking use of this page); its original `?code=` handling
(delivering a ticket via the bot after a web booking — a separate,
older feature) is untouched.

**`seed_phase4_8.py`** — seeds one test customer that books by phone
(like any real guest) and then has an email attached to that *same* user
row (`set_email`), so logging in with that email on `/pages/account.html`
immediately shows the real approved test reservation and its PDF ticket.
Prints a ready-to-use OTP code directly (via
`customer_auth_repo.create_otp`, bypassing the email-sending path) so the
script works identically whether or not `SMTP_*` is configured.

**Verified end-to-end** against a real (fresh, throwaway) SQLite
database with the actual HTTP server running (`python -m api.server`):
schema migration clean (no more "skipped statement" warnings once the
index-ordering bug above was fixed) → `seed_phase4_8.py` → `curl` through
the real flow — invalid email rejected (400), request-otp for a new
address (email printed to server log since `SMTP_HOST` is unset in
`.env.example`), wrong code rejected (401), correct code accepted (200,
real access/refresh tokens), the seeded customer's email login → their
real approved reservation → their real PDF ticket, all matching, and
replaying an already-used OTP code correctly rejected (401). Every
changed Python file `py_compile`s clean; `app.js` and both changed HTML
pages' inline scripts `node --check` clean.

## Follow-up: real Persian ticket typesetting + admin-editable template (schema v7 → v8)

Closes the one item Phase 4-8 explicitly left incomplete ("شکل‌یافته Persian
RTL... reportlab has no built-in RTL/شکل‌دهی support") plus two related,
explicitly requested features: an admin-editable ticket template (with an
optional logo), and per-event "important notes" auto-printed on every
ticket for that event.

**Schema v8** (additive, same discipline as v7): `events.important_notes`
(free text, one consideration per line), `events.ticket_logo` (optional
per-event header logo override), and four new `settings` keys
(`ticket_template_title`, `ticket_template_subtitle`,
`ticket_template_footer`, `ticket_template_logo`).

**`utils/persian_text.py`** (new) — `shape_fa()`: reshapes Persian text into
correctly-joined letterforms (`arabic-reshaper`) and reorders it into visual
order (`python-bidi`'s `get_display`) so a plain LTR `drawString` call
renders it correctly. Degrades to unshaped text (doesn't crash) if the
libraries are missing.

**`assets/fonts/`** (new) — Vazirmatn Regular/Medium/SemiBold/Bold `.ttf`
(same family the website already uses), embedded into the PDF via
reportlab's `TTFont`/`pdfmetrics`. Previously the PDF used bare Helvetica,
which has no Persian glyphs at all.

**`utils/ticket_pdf.py`** (rewritten) — right-to-left layout: event title
and every label/value line right-aligned with word-wrapping against the
right margin; seat count and price rendered in Persian digits (reservation
code stays plain ASCII — it's an identifier, not prose); a new "ملاحظات"
section prints the event's `important_notes` as a bulleted list, wrapped
the same way; header shows the admin-configured template title/subtitle,
or a logo (event-specific `ticket_logo`, falling back to the template's
default `ticket_template_logo`) with the subtitle only — a logo is assumed
to already carry the brand name, so it isn't drawn redundantly alongside a
second text title.

**`api/server.py`** — `_ticket_context()` now also resolves the event's
notes/logo and the global template; new `GET /api/v1/ticket-template`
(public read, same pattern as `/payment-info`) and
`PATCH /api/v1/admin/ticket-template` (admin-only write); `important_notes`
and `ticket_logo` added to the events read/write surface (`_event_public`,
`POST /admin/events`, `PATCH /admin/events/<id>` — already generic via
`update_event_fields`'s whitelist); `/admin/upload` accepts
`kind=ticket_logo`.

**Website admin panel** — `pages/admin/events.html`: per-event "نکات مهم و
ملاحظات" textarea (one note per line) and an optional ticket-logo upload,
alongside the existing poster/gallery/video fields. New
`pages/admin/ticket-template.html`: title/subtitle/footer text + logo
upload with a live header preview, linked from every admin page's sidebar.
`assets/js/app.js`: new `API.ticketTemplate` namespace
(`get`/`update`/`uploadLogo`), mirroring the existing `API.paymentInfo`
public-GET/admin-PATCH split.

**Verified**: every new/changed Python file `py_compile`s clean; every
changed JS file (`app.js` and the two admin pages' inline scripts)
`node --check`s clean; a full run against a fresh test database
(`schema.init_db()` → create event with `important_notes` +
`ticket_logo` → real reservation → `_ticket_context()` →
`build_ticket_pdf()`) produced a correct PDF, rendered to PNG and visually
inspected: Persian text is properly joined/RTL/right-aligned, digits are
Persian, the notes section lists both bullets, and the event-specific logo
(with white card backing, no title-text collision) renders correctly.
Tested both with and without a logo, and with/without notes/address, to
confirm the layout degrades gracefully in each case.

## New tables (schema v7)
- `customer_otp` — hashed OTP codes for customer login (Phase 4)
- `telegram_link_tokens` — one-time deep-link tokens for phone→telegram linking (Phase 4)
- `bot_outbox` — durable queue letting the API process ask the bot process to deliver a Telegram message, since they're separate OS processes sharing only the database (Phase 4/5)
- `messages` — buyer↔admin support chat, one thread per customer (Phase 5)
- `team_members` — "اعضای خانه ماورا" directory (new scope item, modeled on the existing `portfolio` table's shape)
- `reservations.checked_in_at` column — door check-in timestamp (Phase 6)
- New indexes: `idx_reservations_user`, plus one per new table's natural lookup key

## New backend files
- `database/repositories/customer_auth.py`, `bot_outbox.py`, `messages.py`, `team_members.py`
- `services/customer_auth_service.py` — OTP request/verify flow
- `utils/ticket_pdf.py` — PDF ticket generation (reportlab)
- `seed_phase4_8.py` — test data seeding for everything above

## New API endpoints (`api/server.py`)
```
POST /api/v1/auth/customer/request-otp
POST /api/v1/auth/customer/verify-otp
POST /api/v1/auth/customer/refresh
GET  /api/v1/account/reservations
GET  /api/v1/account/reservations/<id>/ticket.pdf
GET  /api/v1/account/messages
POST /api/v1/account/messages
GET  /api/v1/admin/messages
GET  /api/v1/admin/messages/<user_id>
POST /api/v1/admin/messages/<user_id>
GET  /api/v1/team
GET  /api/v1/team/<slug>
POST /api/v1/admin/team
PATCH /api/v1/admin/team/<id>
DELETE /api/v1/admin/team/<id>
POST /api/v1/admin/tickets/verify
POST /api/v1/admin/tickets/checkin
```
All follow the existing routing pattern exactly — no business logic added
to `api/server.py` itself, only to `services/`, per the project's own
architecture rule.

## New frontend pages
- `pages/account.html` — customer login (OTP) + reservation/ticket dashboard + support chat
- `pages/team.html` — public team directory + per-member detail (via `?slug=`)
- `pages/admin/team.html`, `messages.html`, `checkin.html`
- `pages/connect-telegram.html` — extended to also handle `?link=<token>` (account linking), not just `?code=` (existing ticket-delivery flow)

## Bot-side changes
- `utils/scheduler.py` — new `run_outbox_loop()`, polls `bot_outbox` every 5s and delivers via `bot.send_message`
- `bot.py` — registers the new loop alongside the existing expiry/backup loops
- `handlers/common.py` — `/start` now recognizes a `LINK-<token>` deep-link payload and links phone↔telegram_id

## Real bugs found and fixed (not introduced by this work, found while building on top of it)

### 1. Broken site navigation from any inner page
`assets/js/site.js`'s `pp()` path helper returned `index.html` unprefixed
even when called from inside `/pages/`, so clicking the logo or any top
nav link from any non-home page resolved to a 404 (e.g. `/pages/index.html`
instead of `/index.html`). The footer already used a correct, different
convention (`pages/xxx.html` prefix) — the header just never matched it.
Fixed with one added line in `pp()` plus updating the header's `nav` array
to use the same `pages/` prefix convention the footer already used.
Verified with `node --check` and manual path-resolution tracing (a live
browser wasn't available in this sandbox — recommend a quick manual
click-through on your machine to confirm, though the fix is a direct,
traceable correction of the exact reported symptom).

### 2. Website's own "approve reservation" button required aiogram
`services/ticket_service.issue_ticket()` called `utils.qr_generator.generate_qr_png()`,
which imported `aiogram.types.BufferedInputFile` at call time. Since
`issue_ticket()` is shared code (used by both the bot's approve handler
AND the website's `/api/v1/admin/reservations/<id>/approve` endpoint),
this meant approving a reservation from the **website admin panel**
crashed with `No module named 'aiogram'` whenever the API process didn't
have aiogram installed — directly contradicting Phase 1's own stated
design rule that the API-only process should never need a Telegram
dependency. Fixed by having `issue_ticket()` return raw PNG bytes
(`generate_qr_image_bytes()`, aiogram-free) and moving the
`BufferedInputFile` wrapping into the two bot handlers that actually need
it (`handlers/admin_reservations.py`, `handlers/reject_confirmation.py`).
**Verified with a full live test**: create event → session → reservation →
submit receipt → approve → succeeded (previously crashed at this exact
step, confirmed by reproducing the crash first, then re-testing after the
fix).

### 3. Security bug introduced during this work, caught by its own test
`_get_admin_payload()` in `api/server.py` originally only checked
`token type == "access"`. Before customer accounts existed, every valid
access token was necessarily an admin token, so this was safe. Once
`/api/v1/auth/customer/verify-otp` started minting access tokens too, this
check silently accepted a **customer** token on **admin-only** endpoints.
Caught immediately by this project's own testing discipline (curl a
customer token against `/api/v1/admin/reservations` before considering
anything done) — not found by a third party, not shipped. Fixed by
requiring the admin-only `admin_id` claim (a customer token never has
one). Re-verified: customer token → 401 on admin endpoints, admin token →
401 on customer endpoints, admin token → 200 on admin endpoints, customer
token → 200 on customer endpoints.

### 4. `list_for_user()` (customer dashboard) didn't include event/session data
The repository function is a flat, unjoined query (also used by an
existing Phase 1 phone-lookup endpoint, which didn't need event details —
so this wasn't a bug there). The new customer dashboard, though, needs
the event title and session date/time to display anything useful. Fixed
by enriching each row in the API layer using the same lookup helper the
ticket PDF endpoint already uses (`_ticket_context()`), rather than
touching the shared repository function's contract for its other caller.

### 5. `health_check.py`'s table whitelist was missing `web_admins`
Pre-existing gap from Phase 2 — the `web_admins` table (added in Phase 2)
was never added to `health_check.py`'s expected-tables list, so the health
check was silently checking for one fewer table than actually exists.
Added, along with the five new Phase 4-8 tables.

## Known, documented limitations (not fixed — see README's checklist for why)
- Camera-based QR scanning on the check-in page (manual code entry only)
- File attachments in support messages (text only)
- Fully shaped/joined Persian typography in the PDF ticket (reportlab has no built-in Arabic-script shaping)
- A handful of pre-existing admin pages (`events.html` and similar, from Phase 1-3) still build `innerHTML` from admin-supplied fields without the `esc()` helper the new pages use — low real-world risk (admin-only input) but flagged, not silently fixed across many files without your sign-off and real-browser testing
- Full aiogram-installed, real-Telegram-network testing (this sandbox has no internet — same limitation the original Phase 0-3 work documented)

## Testing performed in this sandbox
- Every new/modified Python file: `py_compile` clean
- Every new/modified JS file (inline and external): `node --check` / `new Function()` clean
- Live API server + curl, covering: OTP request (both link-required and
  telegram-delivery paths), OTP verify (correct/incorrect/reuse), token
  role isolation (customer vs admin, all four combinations), full ticket
  lifecycle (create → receipt → approve → verify → check-in → duplicate
  check-in blocked → forged code rejected), messaging (both directions,
  with outbox notification), team CRUD, cross-customer ticket ownership
  isolation
- `health_check.py`: 9/11 (2 failures are expected config-only conditions on a fresh test DB, not bugs)
- `test_bot.py` (existing suite): 42/44 (2 failures are the pre-existing, documented aiogram-not-installed sandbox limitation — zero new regressions)
- `seed_phase4_8.py`: runs clean end-to-end from a fresh database
