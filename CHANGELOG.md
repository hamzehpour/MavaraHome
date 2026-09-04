# CHANGELOG — Phase 4 through 8, + follow-ups (ticket template, email login, split architecture, reservation migration)

Full technical detail behind the summary in `README.md`'s checklist. Schema
went from v6 to v7 (additive only — see `database/schema.py`, every change
is `CREATE TABLE IF NOT EXISTS` or `ALTER TABLE ADD COLUMN`, nothing
dropped or rewritten).

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
