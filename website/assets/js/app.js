/* ══════════════════════════════════════════════
   Maavara Home — App Logic
   Reservation-migration phase 1: back on the unified backend (bot/api/
   server.py) — the same API the Telegram bot itself uses, one database,
   one source of truth for events/portfolio/team AND (as later phases land)
   reservations. website/backend_cms/ (a standalone content-only Flask CMS,
   built when this site briefly needed to run on shared hosting with no
   SSH) is retired — see CHANGELOG.md. Nothing here changed shape because
   of that: backend_cms was deliberately built to answer the exact same
   /api/v1/... routes with the exact same {"data": ...} envelope, so this
   file talks to whichever backend is actually running without caring
   which one it is.
   ══════════════════════════════════════════════ */

const PREFIX = 'mh_';
// The unified API's own origin. Same-origin default ('') works when it's
// deployed under this site's own domain (Nginx proxying /api/v1/ to it —
// see bot/DEPLOYMENT.md). Override via window.MAAVARA_API_BASE only if
// it's genuinely on a different origin/port (e.g. local dev).
const MAVARA_API_BASE = window.MAAVARA_API_BASE || '';
const API_VERSION = 'v1';
const db = {
  get(k) { try { const v = localStorage.getItem(PREFIX + k); return v ? JSON.parse(v) : null } catch { return null } },
  set(k, v) { localStorage.setItem(PREFIX + k, JSON.stringify(v)) },
};

// In-memory cache — deliberately NOT localStorage. Populated by
// API.events.refresh()/API.portfolio.refresh() from the real backend, and
// nothing else ever writes to it directly. This is what makes reads
// (`.all()`, `.get()`) synchronous without persisting anything to the browser.
const cache = { events: [], portfolio: [], sessionsByKey: {} };

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
      // Access tokens are short-lived by design — this is the normal path
      // for "session expired mid-work", not an error case. Try exactly
      // once to refresh and retry before giving up.
      if (err.status === 401 && API.auth.getRefreshToken()) {
        const refreshed = await API.auth.tryRefresh();
        if (refreshed) {
          return apiFetch(path, { ...options, headers: { 'Authorization': `Bearer ${API.auth.getAccessToken()}`, ...(options.headers || {}) } });
        }
      }
      throw err;
    });
}
// Same pattern as apiFetchAdmin, but for a logged-in CUSTOMER (see
// API.customerAuth below) — deliberately separate token storage keys
// (mh_cust_*) from admin's (mh_*) so a browser can hold an admin session
// and a customer session at the same time without either clobbering the
// other's sessionStorage.
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
    active() { return cache.events.filter(e => e.status === 'ongoing' || e.status === 'upcoming') },
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
    async delete(id) {
      await apiFetchAdmin(`/admin/events/${id}`, { method: 'DELETE' });
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
  // Purely client-side (localStorage) — visitor comments on an event,
  // never needed a backend and still don't.
  feedback: {
    byEvent(id) { return (db.get('fb_' + id) || []) },
    add(eventId, data) { const a = this.byEvent(eventId); a.unshift({ ...data, date: new Date().toLocaleDateString('fa-IR') }); db.set('fb_' + eventId, a) }
  },
  // Reservation-migration phase 3: booking goes straight to the real
  // backend — the same reservation_service the Telegram bot uses, same
  // database, immediately visible to the admin either way. No
  // localStorage involved, and no client-side "was this approved?"
  // guessing — status only ever comes from the server.
  reservations: {
    async create({ session_id, phone, full_name, email, people }) {
      return apiFetch('/reservations', {
        method: 'POST',
        body: JSON.stringify({ session_id: Number(session_id), phone, full_name, email, people: Number(people) }),
      });
    },
    async allAdmin() { return apiFetchAdmin('/admin/reservations'); },
    async approve(id) { return apiFetchAdmin(`/admin/reservations/${id}/approve`, { method: 'POST' }); },
    async reject(id, reason) {
      return apiFetchAdmin(`/admin/reservations/${id}/reject`, { method: 'POST', body: JSON.stringify({ reason: reason || '' }) });
    },
  },
  paymentInfo: {
    async get() { return apiFetch('/payment-info'); },
  },
  receipts: {
    async submit(reservationId, dataUrl) {
      return apiFetch(`/reservations/${reservationId}/receipt`, {
        method: 'POST', body: JSON.stringify({ data: dataUrl }),
      });
    },
  },
  // Sessions come straight from the backend — flat rows (event_id, date,
  // time, capacity, available, date_display). `dates` below is a
  // client-side GROUPING of that real list into date cards for the
  // booking widget, not a separate persisted entity — a date only
  // "exists" once it has at least one session, matching the backend's
  // actual shape (there is no dates table).
  sessions: {
    _key(eventId) { return String(eventId); },
    all(eventId) { return cache.sessionsByKey[this._key(eventId)] || []; },
    async refresh(eventId) {
      const rows = await apiFetch(`/sessions?event_id=${encodeURIComponent(eventId)}`);
      cache.sessionsByKey[this._key(eventId)] = rows;
      return rows;
    },
    get(eventId, sessionId) { return this.all(eventId).find(s => String(s.id) === String(sessionId)); },
    forDate(eventId, dateIso) { return this.all(eventId).filter(s => s.date === dateIso).sort((a, b) => a.time.localeCompare(b.time)); },
    remaining(s) { return Math.max(0, Number(s.available)); },
    isFull(s) { return this.remaining(s) <= 0 || s.status === 'sold_out'; },
  },
  dates: {
    /** Groups the (already-fetched, via sessions.refresh) session list for
        one event into date cards. Call API.sessions.refresh(eventId) first. */
    forEvent(eventId) {
      const rows = API.sessions.all(eventId);
      const byDate = {};
      for (const s of rows) { (byDate[s.date] = byDate[s.date] || []).push(s); }
      return Object.keys(byDate).sort().map(dateIso => ({
        id: dateIso, dateIso,
        // date_display comes pre-formatted from the backend (Jalali or
        // Gregorian, per the event's own calendar_type) — see
        // api/server.py's _session_public(). Every session on the same
        // date shares the same display string.
        jalali_date: byDate[dateIso][0].date_display,
        sessions: byDate[dateIso],
      }));
    },
  },
  // Customer account login — currently email-only (see
  // bot/services/customer_auth_service.py). `channel` is sent explicitly
  // even though "email" is also the default server-side, so this file
  // reads as ready for a channel picker once a second channel is ever
  // real, without needing to change again then.
  customerAuth: {
    async requestOtp(email) {
      return apiFetch('/auth/customer/request-otp', { method: 'POST', body: JSON.stringify({ identifier: email, channel: 'email' }) });
    },
    async verifyOtp(email, code) {
      const result = await apiFetch('/auth/customer/verify-otp', { method: 'POST', body: JSON.stringify({ identifier: email, code, channel: 'email' }) });
      sessionStorage.setItem('mh_cust_access_token', result.access_token);
      sessionStorage.setItem('mh_cust_refresh_token', result.refresh_token);
      sessionStorage.setItem('mh_cust_email', email);
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
      sessionStorage.removeItem('mh_cust_email');
    },
    check() { return !!this.getAccessToken(); },
    getAccessToken() { return sessionStorage.getItem('mh_cust_access_token'); },
    getRefreshToken() { return sessionStorage.getItem('mh_cust_refresh_token'); },
    getEmail() { return sessionStorage.getItem('mh_cust_email') || ''; },
  },
  // The logged-in customer's own reservations + ticket PDFs.
  account: {
    async reservations() { return apiFetchCustomer('/account/reservations'); },
    ticketUrl(reservationId) {
      return `${MAVARA_API_BASE}/api/${API_VERSION}/account/reservations/${reservationId}/ticket.pdf`;
    },
  },
  // Tokens live only in sessionStorage (never localStorage, and never
  // persisted server-side beyond the DB row that issued them) — cleared
  // automatically when the browser tab closes, which is the right
  // lifetime for an admin session.
  auth: {
    async login(username, password) {
      const result = await apiFetch('/admin/login', {
        method: 'POST', body: JSON.stringify({ username, password }),
      });
      sessionStorage.setItem('mh_access_token', result.access_token);
      sessionStorage.setItem('mh_refresh_token', result.refresh_token);
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
      sessionStorage.removeItem('mh_username');
    },
    check() { return !!this.getAccessToken(); },
    getAccessToken() { return sessionStorage.getItem('mh_access_token'); },
    getRefreshToken() { return sessionStorage.getItem('mh_refresh_token'); },
  },
  // "اعضای خانه ماورا" team directory.
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
};

// Dark/Light mode. A UI preference, not application data — safe to keep
// in localStorage (unlike events/portfolio, which must always come from
// the shared backend). Applied before first paint where possible (pages
// call this at the top of <body>, not just DOMContentLoaded) to avoid a
// flash of the wrong theme.
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
