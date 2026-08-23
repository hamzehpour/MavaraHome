// Mavara Home · Reservation service — THE single source of truth.
// Website, admin panel and Telegram bot all call this same business logic.
import { store } from './store.js';

export const RESERVATION_STATUSES = [
  'CREATED',
  'AWAITING_PAYMENT',
  'PAYMENT_SUBMITTED',
  'PENDING_ADMIN_CONFIRMATION',
  'CONFIRMED',
  'CANCELLED',
  'REJECTED',
  'WAITING_LIST'
];

export const SESSION_STATUSES = [
  'ACTIVE',
  'INACTIVE',
  'SOLD_OUT',
  'CLOSED',
  'CANCELLED'
];

export function normalizePhone(phone) {
  if (!phone) return '';
  const p2e = s => s.replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)).replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d));
  let p = p2e(phone).replace(/\D/g, '');
  if (p.startsWith('98')) p = '0' + p.slice(2);
  if (p.startsWith('9') && p.length === 10) p = '0' + p;
  return p;
}

export function makeCode() {
  return 'MAV-' + Math.random().toString(36).slice(2, 8).toUpperCase();
}

export function listEvents() { return store.get('events').filter(e => e.status !== 'deleted'); }
export function getEvent(id) { return store.get('events').find(e => e.id === id && e.status !== 'deleted'); }

export function listSessions(date) {
  let rows = store.get('sessions');
  if (date) rows = rows.filter(s => s.date === date);
  return rows.filter(s => s.status !== 'deleted').map(sessionView);
}

function sessionView(s) {
  const reserved = reservedCountFor(s.id);
  const available = Math.max(0, s.capacity - reserved);
  let status = s.status;
  if (status === 'ACTIVE' && available <= 0) status = 'SOLD_OUT';
  return { ...s, reserved_count: reserved, available_capacity: available, status };
}

export function reservedCountFor(sessionId) {
  return store.get('reservations')
    .filter(r => r.session_id === sessionId && ['AWAITING_PAYMENT', 'PAYMENT_SUBMITTED', 'PENDING_ADMIN_CONFIRMATION', 'CONFIRMED'].includes(r.status))
    .reduce((sum, r) => sum + Number(r.count || 1), 0);
}

export function reserve({ session_id, user, count = 1, source = 'website' }) {
  const session = store.get('sessions').find(s => s.id === session_id && s.status !== 'deleted');
  if (!session) return { error: 'session_not_found' };
  
  const currentView = sessionView(session);
  if (currentView.status === 'SOLD_OUT' || currentView.status === 'CLOSED' || currentView.status === 'CANCELLED') {
    return { error: 'session_unavailable', status: currentView.status };
  }

  if (!user?.name || !user?.phone) return { error: 'validation', details: 'name and phone are required' };
  
  const phone = normalizePhone(user.phone);
  const n = Math.max(1, Number(count) | 0);
  
  if (n > currentView.available_capacity) {
    return { error: 'sold_out', available: currentView.available_capacity };
  }

  const event = getEvent(session.event_id);
  if (!event) return { error: 'event_not_found' };

  let userRec = store.get('users').find(u => u.phone === phone);
  if (!userRec) {
    userRec = { id: store.uid(), name: user.name, phone: phone, telegram_id: user.telegram_id || null, created_at: new Date().toISOString() };
    store.set('users', [...store.get('users'), userRec]);
  }

  const reservation = { 
    id: store.uid(), reservation_code: makeCode(), user_id: userRec.id, session_id: session.id, 
    count: n, unit_price: Number(event.price || 0), total_price: n * Number(event.price || 0), 
    status: 'AWAITING_PAYMENT', source, admin_note: null, created_at: new Date().toISOString() 
  };
  
  store.set('reservations', [...store.get('reservations'), reservation]);
  store.set('reservation_events', [...(store.get('reservation_events') || []), { reservation_id: reservation.id, status: 'CREATED', at: new Date().toISOString() }]);
  return { reservation, session: sessionView(session), event: { id: event.id, title: event.title } };
}

export function joinWaitingList({ session_id, user }) {
  const session = store.get('sessions').find(s => s.id === session_id && s.status !== 'deleted');
  if (!session) return { error: 'session_not_found' };
  if (!user?.name || !user?.phone) return { error: 'validation', details: 'name and phone are required' };

  const phone = normalizePhone(user.phone);
  let userRec = store.get('users').find(u => u.phone === phone);
  if (!userRec) {
    userRec = { id: store.uid(), name: user.name, phone: phone, telegram_id: user.telegram_id || null, created_at: new Date().toISOString() };
    store.set('users', [...store.get('users'), userRec]);
  }

  const reservation = {
    id: store.uid(), reservation_code: makeCode(), user_id: userRec.id, session_id,
    count: 1, unit_price: 0, total_price: 0, status: 'WAITING_LIST', source: 'website',
    admin_note: 'waiting list', created_at: new Date().toISOString(),
  };
  store.set('reservations', [...store.get('reservations'), reservation]);
  store.set('reservation_events', [...(store.get('reservation_events') || []), { reservation_id: reservation.id, status: 'WAITING_LIST', at: new Date().toISOString() }]);
  return { reservation };
}

export function uploadReceipt(id, { image, note }) {
  const r = store.get('reservations').find(x => x.id === id || x.reservation_code === id);
  if (!r) return { error: 'not_found' };
  if (!image) return { error: 'validation', details: 'receipt image is required' };
  // Regression fix: V9 rejected oversized receipts (>1.5MB) to protect the
  // JSON-file store from bloating on a single upload; this check was lost
  // in an earlier rewrite. Restored with the same limit.
  if (image.length > 1_500_000) return { error: 'receipt_too_large' };
  if (!['AWAITING_PAYMENT', 'PAYMENT_SUBMITTED', 'REJECTED'].includes(r.status)) return { error: 'invalid_status' };

  r.status = 'PAYMENT_SUBMITTED';
  r.receipt_at = new Date().toISOString();
  
  const payment = { id: store.uid(), reservation_id: r.id, amount: r.total_price, status: 'SUBMITTED', receipt_image: image, admin_note: note || null, created_at: new Date().toISOString() };
  store.set('payments', [...(store.get('payments') || []), payment]);
  store.set('reservation_events', [...(store.get('reservation_events') || []), { reservation_id: r.id, status: 'PAYMENT_SUBMITTED', at: new Date().toISOString() }]);
  store.persist();
  return { reservation: r, payment };
}

export function setStatus(id, { status, note, actor }) {
  if (!RESERVATION_STATUSES.includes(status)) return { error: 'invalid_status' };
  const r = store.get('reservations').find(x => x.id === id || x.reservation_code === id);
  if (!r) return { error: 'not_found' };
  
  const oldStatus = r.status;
  r.status = status;
  if (note !== undefined) r.admin_note = note;
  
  store.set('audit', [...store.get('audit'), { actor: actor || 'admin', action: `status_change: ${oldStatus} -> ${status}`, reservation_id: r.id, at: new Date().toISOString() }]);
  store.set('reservation_events', [...(store.get('reservation_events') || []), { reservation_id: r.id, status: status, at: new Date().toISOString() }]);
  store.persist();
  return { reservation: r };
}

export function getReservation(id) { return store.get('reservations').find(r => r.id === id || r.reservation_code === id); }

export function listReservations() {
  const res = store.get('reservations');
  const sessions = store.get('sessions');
  const events = store.get('events');
  const users = store.get('users');

  return res.map(r => {
    const s = sessions.find(x => x.id === r.session_id);
    const e = events.find(x => x.id === (s ? s.event_id : r.event_id));
    const u = users.find(x => x.id === r.user_id);
    return { ...r, event_id: e ? e.id : null, event_title: e ? e.title : 'Unknown', session_info: s ? `${s.date} — ${s.time}` : 'Unknown', name: u ? u.name : r.name, phone: u ? u.phone : r.phone };
  }).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
}

export function listPortfolio() {
  return store.get('portfolio') || [];
}

// Minimal Gregorian → Jalali conversion (no external deps available in this
// runtime). Was previously hardcoded to a single demo date, which silently
// made "today's" dashboard numbers wrong on every day except that one.
function todayJalali() {
  const d = new Date();
  const gy = d.getFullYear(), gm = d.getMonth() + 1, gd = d.getDate();
  const g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
  let jy = gy <= 1600 ? 0 : 979;
  const gy2 = gy <= 1600 ? gy - 621 : gy - 1600;
  const gy3 = gm > 2 ? gy2 + 1 : gy2;
  let days = 365 * gy2 + Math.floor((gy3 + 3) / 4) - Math.floor((gy3 + 99) / 100) +
    Math.floor((gy3 + 399) / 400) - 80 + gd + g_d_m[gm - 1];
  jy += 33 * Math.floor(days / 12053); days %= 12053;
  jy += 4 * Math.floor(days / 1461); days %= 1461;
  if (days > 365) { jy += Math.floor((days - 1) / 365); days = (days - 1) % 365; }
  const jm = days < 186 ? 1 + Math.floor(days / 31) : 7 + Math.floor((days - 186) / 30);
  const jd = 1 + (days < 186 ? days % 31 : (days - 186) % 30);
  return `${jy}-${String(jm).padStart(2, '0')}-${String(jd).padStart(2, '0')}`;
}

export function getDashboardStats() {
  const reservations = store.get('reservations');
  const sessions = listSessions();
  const today = todayJalali();
  const newReservations = reservations.filter(r => r.status === 'CREATED').length;
  const pendingReview = reservations.filter(r => r.status === 'PAYMENT_SUBMITTED').length;
  const confirmedSales = reservations.filter(r => r.status === 'CONFIRMED').reduce((sum, r) => sum + r.total_price, 0);
  const todaySessions = sessions.filter(s => s.date === today);
  const remainingCapacity = todaySessions.reduce((sum, s) => sum + s.available_capacity, 0);
  const soldOutSessions = todaySessions.filter(s => s.status === 'SOLD_OUT').length;

  return {
    today: { new_reservations: newReservations, pending_review: pendingReview, sales: confirmedSales, remaining_capacity: remainingCapacity, sold_out_sessions: soldOutSessions },
    action_required: { receipts_pending: pendingReview },
    sessions_today: todaySessions
  };
}
