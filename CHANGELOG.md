# CHANGELOG — Phase 4 through 8, + follow-ups (ticket template, email login, split architecture)

Full technical detail behind the summary in `README.md`'s checklist. Schema
went from v6 to v7 (additive only — see `database/schema.py`, every change
is `CREATE TABLE IF NOT EXISTS` or `ALTER TABLE ADD COLUMN`, nothing
dropped or rewritten).

## Follow-up: split website/ from bot/ so the site can host on plain shared hosting (no SSH)

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
