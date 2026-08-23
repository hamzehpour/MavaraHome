/* ══════════════════════════════════════════════
   Maavara Home — App Logic
   Phase 1 (backend unification): events/sessions/reservations are now
   backed by the real unified Python API (api/server.py in the bot
   project) — NOT localStorage. Two browsers now see the same events and
   the same reservations, and so does the Telegram bot, because all three
   write to the same SQLite database. Portfolio/settings/admin-auth remain
   on localStorage for now — that migration is explicitly a later phase
   (see the project handoff doc), not silently skipped.
   ══════════════════════════════════════════════ */

const PREFIX = 'mh_';
// The unified backend (Python, api/server.py) — NOT the old Node
// backend/server.js, which only ever served static files + the old
// mock/localStorage-shaped API. Override via window.MAAVARA_API_BASE for
// a real deployment (e.g. https://api.mavara-home.com).
// Production (Nginx reverse-proxying /api/v1/ on the same domain — see
// deploy/nginx.conf.example): same-origin, so '' (empty) is correct and
// is the default. Local development: run the API's built-in STATIC_ROOT
// mode (`STATIC_ROOT=/path/to/this/site python -m api.server`) so the
// site and API are on the SAME port (8788) too — same-origin '' still
// works, no override needed. Only set window.MAAVARA_API_BASE explicitly
// if serving the static files from a genuinely different origin/port than
// the API (e.g. quick testing with two separate dev servers).
const MAVARA_API_BASE = window.MAAVARA_API_BASE || '';
const API_VERSION = 'v1';
const db = {
  get(k) { try { const v = localStorage.getItem(PREFIX + k); return v ? JSON.parse(v) : null } catch { return null } },
  set(k, v) { localStorage.setItem(PREFIX + k, JSON.stringify(v)) },
  uid() { return 'mv-' + Date.now().toString(36) + '-' + Math.random().toString(36).substr(2, 6) }
};

// In-memory cache — deliberately NOT localStorage. Populated by
// API.events.refresh()/sessions.refresh() from the real backend, and nothing
// else ever writes to it directly. This is what makes reads (`.all()`,
// `.get()`) synchronous without persisting anything to the browser.
const cache = { events: [], sessionsByKey: {}, portfolio: [] };

async function apiFetch(path, options = {}) {
  const res = await fetch(`${MAVARA_API_BASE}/api/${API_VERSION}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  });
  let body;
  try { body = await res.json(); } catch { body = {}; }
  if (!res.ok) {
    const err = new Error(body.error || `API error ${res.status}`);
    err.status = res.status; err.details = body.details;
    throw err;
  }
  return body.data;
}
function apiFetchAdmin(path, options = {}) {
  return apiFetch(path, { ...options, headers: { 'Authorization': `Bearer ${API.auth.getAccessToken() || ''}`, ...(options.headers || {}) } })
    .catch(async (err) => {
      // Access tokens are short-lived (15 min) by design — this is the
      // normal path for "session expired mid-work", not an error case.
      // Try exactly once to refresh and retry before giving up.
      if (err.status === 401 && API.auth.getRefreshToken()) {
        const refreshed = await API.auth.tryRefresh();
        if (refreshed) {
          return apiFetch(path, { ...options, headers: { 'Authorization': `Bearer ${API.auth.getAccessToken()}`, ...(options.headers || {}) } });
        }
      }
      throw err;
    });
}

function apiFetchCustomer(path, options = {}) {
  return apiFetch(path, { ...options, headers: { 'Authorization': `Bearer ${API.customerAuth.getAccessToken() || ''}`, ...(options.headers || {}) } })
    .catch(async (err) => {
      if (err.status === 401 && API.customerAuth.getRefreshToken()) {
        const refreshed = await API.customerAuth.tryRefresh();
        if (refreshed) {
          return apiFetch(path, { ...options, headers: { 'Authorization': `Bearer ${API.customerAuth.getAccessToken()}`, ...(options.headers || {}) } });
        }
      }
      throw err;
    });
}

// ── API ──
const API = {
  async init() {
    // Events and portfolio now come from the real backend on every page
    // load — this is the actual fix for "two browsers see different
    // data" and "resume content isn't really admin-editable". A network
    // failure here is surfaced (see callers), never silently backfilled
    // with fake local data.
    try {
      await API.events.refresh();
    } catch (e) {
      console.error('Failed to load events from backend:', e);
    }
    try {
      await API.portfolio.refresh();
    } catch (e) {
      console.error('Failed to load portfolio from backend:', e);
    }
  },
  events: {
    all() { return cache.events },
    active() { return cache.events.filter(e => e.is_active) },
    get(id) { return cache.events.find(e => String(e.id) === String(id)) },
    async refresh() { cache.events = await apiFetch('/events'); return cache.events; },
    async create(d) {
      const created = await apiFetchAdmin('/admin/events', { method: 'POST', body: JSON.stringify(d) });
      await this.refresh();
      return created;
    },
    async update(id, d) {
      const updated = await apiFetchAdmin(`/admin/events/${id}`, { method: 'PATCH', body: JSON.stringify(d) });
      await this.refresh();
      return updated;
    },
    async setActive(id, isActive) { return this.update(id, { is_active: isActive }); },
    async uploadMedia(file, kind) {
      const dataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
      const result = await apiFetchAdmin('/admin/upload', {
        method: 'POST', body: JSON.stringify({ data: dataUrl, filename: file.name, kind }),
      });
      return result.path;
    },
  },
  portfolio: {
    all() { return cache.portfolio || [] },
    byCat(c) { return this.all().filter(p => p.category === c).sort((a, b) => b.year - a.year) },
    get(id) { return this.all().find(p => String(p.id) === String(id)) },
    async refresh() { cache.portfolio = await apiFetch('/portfolio'); return cache.portfolio; },
    async create(d) {
      const created = await apiFetchAdmin('/admin/portfolio', { method: 'POST', body: JSON.stringify(d) });
      await this.refresh();
      return created;
    },
    async update(id, d) {
      const updated = await apiFetchAdmin(`/admin/portfolio/${id}`, { method: 'PATCH', body: JSON.stringify(d) });
      await this.refresh();
      return updated;
    },
    async delete(id) {
      await apiFetchAdmin(`/admin/portfolio/${id}`, { method: 'DELETE' });
      await this.refresh();
    },
    async uploadMedia(file, kind) {
      const dataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
      const result = await apiFetchAdmin('/admin/upload', {
        method: 'POST', body: JSON.stringify({ data: dataUrl, filename: file.name, kind: 'portfolio' }),
      });
      return result.path;
    },
  },
  feedback: {
    byEvent(id) { return (db.get('fb_' + id) || []) },
    add(eventId, data) { const a = this.byEvent(eventId); a.unshift({ ...data, date: new Date().toLocaleDateString('fa-IR') }); db.set('fb_' + eventId, a) }
  },
  // Reservations now go straight to the unified backend — this is the
  // actual fix for "reservation from the website isn't visible to the
  // bot/admin". No localStorage involved at all.
  reservations: {
    async create({ session_id, phone, full_name, people }) {
      return apiFetch('/reservations', {
        method: 'POST',
        body: JSON.stringify({ session_id: Number(session_id), phone, full_name, people: Number(people) }),
      });
    },
    async byPhone(phone) {
      return apiFetch(`/reservations?phone=${encodeURIComponent(phone)}`);
    },
    async allAdmin() {
      return apiFetchAdmin('/admin/reservations');
    },
    async approve(id) {
      return apiFetchAdmin(`/admin/reservations/${id}/approve`, { method: 'POST' });
    },
    async reject(id, reason) {
      return apiFetchAdmin(`/admin/reservations/${id}/reject`, { method: 'POST', body: JSON.stringify({ reason: reason || '' }) });
    },
  },
  paymentInfo: {
    async get() { return apiFetch('/payment-info'); },
    async set(d) { return apiFetchAdmin('/admin/payment-info', { method: 'POST', body: JSON.stringify(d) }); },
  },
  receipts: {
    async submit(reservationId, dataUrl) {
      return apiFetch(`/reservations/${reservationId}/receipt`, {
        method: 'POST', body: JSON.stringify({ data: dataUrl }),
      });
    },
  },
  // Sessions come from the real backend now — flat rows (event_id, date,
  // time, capacity), no separate "dates" table server-side (unlike the old
  // localStorage shape). `dates` below is a client-side GROUPING of the
  // real session list, not a separate persisted entity — see calendar.html
  // for how the admin UI adapted to this (a date only "exists" once it has
  // at least one session, matching the real backend's actual shape).
  sessions: {
    _key(eventId) { return String(eventId); },
    all(eventId) { return cache.sessionsByKey[this._key(eventId)] || []; },
    async refresh(eventId) {
      const rows = await apiFetchAdmin(`/sessions?event_id=${encodeURIComponent(eventId)}`);
      cache.sessionsByKey[this._key(eventId)] = rows;
      return rows;
    },
    get(eventId, sessionId) { return this.all(eventId).find(s => String(s.id) === String(sessionId)); },
    forDate(eventId, dateIso) { return this.all(eventId).filter(s => s.date === dateIso).sort((a, b) => a.time.localeCompare(b.time)); },
    async create(eventId, { dateIso, time, capacity }) {
      const created = await apiFetchAdmin('/admin/sessions', {
        method: 'POST', body: JSON.stringify({ event_id: Number(eventId), date: dateIso, time, capacity: Number(capacity) }),
      });
      await this.refresh(eventId);
      return created;
    },
    async setStatus(eventId, sessionId, status) {
      const updated = await apiFetchAdmin(`/admin/sessions/${sessionId}`, { method: 'PATCH', body: JSON.stringify({ status }) });
      await this.refresh(eventId);
      return updated;
    },
    async delete(eventId, sessionId) {
      await apiFetchAdmin(`/admin/sessions/${sessionId}`, { method: 'DELETE' });
      await this.refresh(eventId);
    },
    remaining(s) { return Math.max(0, Number(s.available)); },
    isFull(s) { return this.remaining(s) <= 0 || s.status === 'sold_out'; }
  },
  dates: {
    /** Groups the (already-fetched, via sessions.refresh) session list for
        one event into date cards — this is a view over real data, not a
        separate localStorage collection. Call API.sessions.refresh(eventId)
        first (or rely on it having been called already). */
    forEvent(eventId) {
      const rows = API.sessions.all(eventId);
      const byDate = {};
      for (const s of rows) { (byDate[s.date] = byDate[s.date] || []).push(s); }
      return Object.keys(byDate).sort().map(dateIso => {
        const [gy, gm, gd] = dateIso.split('-').map(Number);
        const { jy, jm, jd } = MavaraCal.gregorianToJalali(gy, gm, gd);
        return { id: dateIso, dateIso, jalali_date: MavaraCal.formatJalali(jy, jm, jd), sessions: byDate[dateIso] };
      });
    }
  },
  settings: {
    get(key) { const s = db.get('settings') || {}; return key ? s[key] : s; },
    set(patch) { db.set('settings', { ...(db.get('settings') || {}), ...patch }); }
  },
  // Phase 2: real authentication. Tokens live only in sessionStorage (never
  // localStorage, and never persisted server-side beyond the DB row that
  // issued them) — cleared automatically when the browser tab closes,
  // which is the right lifetime for an admin session.
  auth: {
    async login(username, password) {
      const result = await apiFetch('/admin/login', {
        method: 'POST', body: JSON.stringify({ username, password }),
      });
      sessionStorage.setItem('mh_access_token', result.access_token);
      sessionStorage.setItem('mh_refresh_token', result.refresh_token);
      sessionStorage.setItem('mh_role', result.role);
      sessionStorage.setItem('mh_username', result.username);
      return result;
    },
    async tryRefresh() {
      const refreshToken = this.getRefreshToken();
      if (!refreshToken) return false;
      try {
        const result = await apiFetch('/admin/refresh', {
          method: 'POST', body: JSON.stringify({ refresh_token: refreshToken }),
        });
        sessionStorage.setItem('mh_access_token', result.access_token);
        return true;
      } catch {
        this.logout();
        return false;
      }
    },
    logout() {
      sessionStorage.removeItem('mh_access_token');
      sessionStorage.removeItem('mh_refresh_token');
      sessionStorage.removeItem('mh_role');
      sessionStorage.removeItem('mh_username');
    },
    check() { return !!this.getAccessToken(); },
    getAccessToken() { return sessionStorage.getItem('mh_access_token'); },
    getRefreshToken() { return sessionStorage.getItem('mh_refresh_token'); },
  },
  // Phase 4: customer accounts. Deliberately separate token storage keys
  // (mh_cust_*) from admin's (mh_*) so a browser can be logged into an
  // admin session and a customer session at the same time without either
  // clobbering the other's sessionStorage — and so a customer token can
  // never accidentally get sent to an admin-only endpoint by reusing the
  // same getAccessToken() the admin panel uses (see api/server.py's
  // _get_admin_payload — it explicitly rejects a customer token anyway,
  // but keeping the two storages separate avoids relying on that as the
  // only safety net).
  customerAuth: {
    async requestOtp(phone) {
      return apiFetch('/auth/customer/request-otp', { method: 'POST', body: JSON.stringify({ phone }) });
    },
    async verifyOtp(phone, code) {
      const result = await apiFetch('/auth/customer/verify-otp', { method: 'POST', body: JSON.stringify({ phone, code }) });
      sessionStorage.setItem('mh_cust_access_token', result.access_token);
      sessionStorage.setItem('mh_cust_refresh_token', result.refresh_token);
      sessionStorage.setItem('mh_cust_phone', result.phone || phone);
      sessionStorage.setItem('mh_cust_name', result.full_name || '');
      return result;
    },
    async tryRefresh() {
      const refreshToken = this.getRefreshToken();
      if (!refreshToken) return false;
      try {
        const result = await apiFetch('/auth/customer/refresh', { method: 'POST', body: JSON.stringify({ refresh_token: refreshToken }) });
        sessionStorage.setItem('mh_cust_access_token', result.access_token);
        return true;
      } catch {
        this.logout();
        return false;
      }
    },
    logout() {
      sessionStorage.removeItem('mh_cust_access_token');
      sessionStorage.removeItem('mh_cust_refresh_token');
      sessionStorage.removeItem('mh_cust_phone');
      sessionStorage.removeItem('mh_cust_name');
    },
    check() { return !!this.getAccessToken(); },
    getAccessToken() { return sessionStorage.getItem('mh_cust_access_token'); },
    getRefreshToken() { return sessionStorage.getItem('mh_cust_refresh_token'); },
    getPhone() { return sessionStorage.getItem('mh_cust_phone') || ''; },
    getName() { return sessionStorage.getItem('mh_cust_name') || ''; },
  },
  // Phase 4/6: the logged-in customer's own reservations + ticket PDFs.
  account: {
    async reservations() { return apiFetchCustomer('/account/reservations'); },
    ticketUrl(reservationId) {
      return `${MAVARA_API_BASE}/api/${API_VERSION}/account/reservations/${reservationId}/ticket.pdf`;
    },
  },
  // Phase 5: buyer <-> admin messaging.
  messages: {
    async mine() { return apiFetchCustomer('/account/messages'); },
    async send(body) { return apiFetchCustomer('/account/messages', { method: 'POST', body: JSON.stringify({ body }) }); },
    async adminThreads() { return apiFetchAdmin('/admin/messages'); },
    async adminThread(userId) { return apiFetchAdmin(`/admin/messages/${userId}`); },
    async adminReply(userId, body) { return apiFetchAdmin(`/admin/messages/${userId}`, { method: 'POST', body: JSON.stringify({ body }) }); },
  },
  // New scope: "اعضای خانه ماورا" team directory.
  team: {
    async all() { return apiFetch('/team'); },
    async bySlug(slug) { return apiFetch(`/team/${encodeURIComponent(slug)}`); },
    async adminAll() { return apiFetchAdmin('/team'); },
    async create(d) { return apiFetchAdmin('/admin/team', { method: 'POST', body: JSON.stringify(d) }); },
    async update(id, d) { return apiFetchAdmin(`/admin/team/${id}`, { method: 'PATCH', body: JSON.stringify(d) }); },
    async delete(id) { return apiFetchAdmin(`/admin/team/${id}`, { method: 'DELETE' }); },
    async uploadMedia(file) {
      const dataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
      const result = await apiFetchAdmin('/admin/upload', { method: 'POST', body: JSON.stringify({ data: dataUrl, filename: file.name, kind: 'team' }) });
      return result.path;
    },
  },
  // Phase 6: door check-in / ticket verification (admin only).
  tickets: {
    async verify(payload) { return apiFetchAdmin('/admin/tickets/verify', { method: 'POST', body: JSON.stringify({ payload }) }); },
    async checkin(payload) { return apiFetchAdmin('/admin/tickets/checkin', { method: 'POST', body: JSON.stringify({ payload }) }); },
  }
};

// Phase 3: Dark/Light mode. A UI preference, not application data — safe
// to keep in localStorage (unlike events/reservations/portfolio, which
// must always come from the shared backend). Applied before first paint
// where possible (pages call this at the top of <body>, not just
// DOMContentLoaded) to avoid a flash of the wrong theme.
const MavaraTheme = {
  KEY: 'mh_theme',
  get() { return localStorage.getItem(this.KEY) || 'light'; },
  apply(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(this.KEY, theme);
  },
  toggle() { this.apply(this.get() === 'dark' ? 'light' : 'dark'); },
  init() { this.apply(this.get()); },
};
MavaraTheme.init();
