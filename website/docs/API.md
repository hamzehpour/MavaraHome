# Mavara Home API — v1

Base: `http://localhost:8787/api/v1` — set `window.MAAVARA_API_BASE` in frontend, or `MAAVARA_API_BASE` env for the bot. OpenAPI contract: `backend/openapi.json`.

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | /events | – | Active events |
| GET | /events/:id | – | One event |
| GET | /sessions?date=1405-05-15 | – | Sessions with server-computed available_capacity |
| POST | /reservations | – | Create reservation (capacity checked server-side; 409 sold_out) |
| POST | /reservations `{waiting_list:true}` | – | Join waiting list |
| GET | /reservations/:id | – | Reservation by id or code (MAV-XXXXXX) |
| POST | /payments/receipt | – | Upload receipt (image data-URL ≤ ~1.5MB) → receipt_uploaded |
| PATCH | /reservations/:id/status | X-Admin-Token | approve/reject/cancel + note (audit logged) |
| POST | /auth/login | – | Session handshake (token compare server-side only) |

Statuses (single source of truth): `pending_payment → receipt_uploaded → waiting_admin_confirmation → approved | rejected`, plus `cancelled` and `waiting` (waiting list). The Telegram bot must call these exact endpoints.
