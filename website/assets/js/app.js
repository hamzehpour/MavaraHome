/* ══════════════════════════════════════════════
   Maavara Home — App Logic
   Split architecture: this site is CONTENT ONLY (events, resume, team) —
   backed by its own small Flask/WSGI CMS (backend_cms/), deployable on
   ordinary shared hosting (cPanel/DirectAdmin "Setup Python App", no SSH
   needed). Reservation, payment, tickets, and customer accounts are
   entirely the Telegram bot's responsibility (bot/) — a separate project
   on separate hosting, with its own database. Nothing here talks to it;
   "booking" on this site is just a link to Telegram/phone, same as the
   original brief before the reservation platform existed.
   ══════════════════════════════════════════════ */

const PREFIX = 'mh_';
// backend_cms's own origin. Same-origin default ('') works when the CMS
// is deployed under this site's own domain (e.g. proxied under /api/ —
// see backend_cms/DEPLOYMENT.md). Override via window.MAAVARA_API_BASE
// only if the CMS is genuinely on a different origin/port.
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
const cache = { events: [], portfolio: [] };

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
