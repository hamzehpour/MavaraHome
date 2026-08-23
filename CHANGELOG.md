# CHANGELOG — Phase 4 through 8, + follow-up (ticket template)

Full technical detail behind the summary in `README.md`'s checklist. Schema
went from v6 to v7 (additive only — see `database/schema.py`, every change
is `CREATE TABLE IF NOT EXISTS` or `ALTER TABLE ADD COLUMN`, nothing
dropped or rewritten).

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
