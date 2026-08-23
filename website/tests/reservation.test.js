// Mavara Home · business logic tests (run: node tests/reservation.test.js)
// Updated for V12's status vocabulary (CREATED/AWAITING_PAYMENT/... instead
// of V9's lowercase pending_payment/receipt_uploaded/...) — see backend/src/service.js.
import { reserve, listSessions, uploadReceipt, setStatus, getReservation, joinWaitingList } from '../backend/src/service.js';
import { store } from '../backend/src/store.js';

let pass = 0, fail = 0;
function assert(name, cond) { if (cond) { pass++; console.log('PASS', name); } else { fail++; console.log('FAIL', name); } }

// Fresh state
store.load().reservations = []; store.persist();
const session = listSessions()[0];

// 1. Happy path
const r1 = reserve({ session_id: session.id, user: { name: 'تست', phone: '09120000001' }, count: 2 });
assert('successful reservation returns code MAV-', r1.reservation && /^MAV-[A-Z0-9]{6}$/.test(r1.reservation.reservation_code));
assert('total price = count x price', r1.reservation.total_price === 2 * 150000);
assert('status AWAITING_PAYMENT', r1.reservation.status === 'AWAITING_PAYMENT');

// 2. Capacity: fill the session (capacity 20; already 2 reserved → request 19 must fail)
const r2 = reserve({ session_id: session.id, user: { name: 'تست۲', phone: '09120000002' }, count: 19 });
assert('over-capacity returns sold_out', r2.error === 'sold_out');

// 3. Waiting list (regression test — this call used to crash: joinWaitingList
// was referenced by server.js but not exported by service.js at all)
const w = joinWaitingList({ session_id: session.id, user: { name: 'صف', phone: '09120000003' } });
assert('waiting list status WAITING_LIST', w.reservation && w.reservation.status === 'WAITING_LIST');

// 4. Receipt flow
const up = uploadReceipt(r1.reservation.id, { image: 'data:image/png;base64,AAAA' });
assert('receipt upload → PAYMENT_SUBMITTED', up.reservation && up.reservation.status === 'PAYMENT_SUBMITTED');
// Regression test: this validation existed in V9 but was silently dropped
// in a later rewrite; restored in service.js.
assert('oversized receipt rejected', uploadReceipt(r1.reservation.id, { image: 'x'.repeat(2_000_000) }).error === 'receipt_too_large');

// 5. Admin approve + audit
setStatus(r1.reservation.id, { status: 'PENDING_ADMIN_CONFIRMATION', actor: 'test-admin' });
const fin = setStatus(r1.reservation.id, { status: 'CONFIRMED', actor: 'test-admin' });
assert('approve flow works', fin.reservation && fin.reservation.status === 'CONFIRMED');
assert('audit logged', store.get('audit').some(a => a.reservation_id === r1.reservation.id && a.action.includes('CONFIRMED')));

// 6. Deleted session → error
store.get('sessions')[0].status = 'deleted'; store.persist();
const r3 = reserve({ session_id: session.id, user: { name: 'x', phone: '09120000004' }, count: 1 });
assert('deleted session rejected', r3.error === 'session_not_found');
store.get('sessions')[0].status = 'ACTIVE'; store.persist();

// 7. Lookup by code
assert('lookup by reservation code', getReservation(r1.reservation.reservation_code).id === r1.reservation.id);

// 8. Regression: creating a new session, then reserving on it, must work
// end-to-end — this is the exact scenario the project owner asked to be
// verified ("create an event/session → reservations on it must work").
const freshSession = { id: 'test-new-session', event_id: session.event_id, date: '1405-06-01', time: '21:00', capacity: 5, status: 'ACTIVE' };
store.set('sessions', [...store.get('sessions'), freshSession]);
const r4 = reserve({ session_id: freshSession.id, user: { name: 'رزرو رویداد جدید', phone: '09120000005' }, count: 3 });
assert('reservation on a freshly created session works', r4.reservation && r4.reservation.status === 'AWAITING_PAYMENT');
assert('capacity tracked correctly on new session', r4.session.available_capacity === 2);

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
