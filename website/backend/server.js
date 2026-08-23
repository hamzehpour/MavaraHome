// ⚠️ DEPRECATED as of Phase 1 (backend unification): this Node backend is
// NO LONGER the site's real data source. The frontend (assets/js/app.js)
// now talks to the Python API in the Telegram bot project (api/server.py)
// instead — that's the single shared backend for the website, admin
// panel, AND the Telegram bot. Running this Node server will NOT sync
// with the bot; anything created through it is invisible everywhere else.
// Kept in the repo only for historical reference. See DEPLOYMENT.md (in
// the bot project) for the real production setup.
//
// Mavara Home · REST API server (Node, zero dependencies)
// GET  /api/v1/events | /events/:id | /sessions?date= | /reservations/:id
// POST /api/v1/reservations | /payments/receipt | /auth/login
// PATCH /api/v1/reservations/:id/status   (admin, requires X-Admin-Token)
import http from 'node:http';
import { readFileSync, existsSync, statSync, writeFileSync, mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { store } from './src/store.js';
import { 
  listEvents, getEvent, listSessions, reserve, joinWaitingList, 
  getReservation, uploadReceipt, setStatus, getDashboardStats, listReservations,
  listPortfolio
} from './src/service.js';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Simple .env loader
const envFile = join(__dirname, '.env.local');
if (existsSync(envFile)) {
  const content = readFileSync(envFile, 'utf8');
  content.split('\n').forEach(line => {
    const [key, value] = line.split('=');
    if (key && value) process.env[key.trim()] = value.trim();
  });
}

const PORT = Number(process.env.PORT || 8787);
const ADMIN_TOKEN = process.env.MAVARA_ADMIN_TOKEN || '1234';
const SITE_ROOT = join(__dirname, '..'); // project root: index.html, pages/, assets/ all live here

const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml',
  '.woff': 'font/woff', '.woff2': 'font/woff2', '.ico': 'image/x-icon',
};

function serveStatic(req, res, pathname) {
  // Serves index.html, pages/*.html, assets/* from the same origin as the
  // API so the frontend never needs CORS and can call /api/v1/... with a
  // plain relative fetch. Also means one `node server.js` is the entire
  // deployable — no separate static host to keep in sync.
  let relPath = pathname === '/' ? '/index.html' : pathname;
  const filePath = join(SITE_ROOT, relPath);
  if (!filePath.startsWith(SITE_ROOT) || !existsSync(filePath) || !isFile(filePath)) {
    return json(res, 404, { error: 'not_found' });
  }
  const ext = filePath.slice(filePath.lastIndexOf('.'));
  res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
  res.end(readFileSync(filePath));
}
function isFile(p) { try { return statSync(p).isFile(); } catch { return false; } }

function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PATCH,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type,X-Admin-Token');
}
function json(res, code, body) { res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' }); res.end(JSON.stringify(body)); }
function readBody(req, maxBytes = 2_000_000) { return new Promise(resolve => { let d = ''; req.on('data', c => { d += c; if (d.length > maxBytes) req.destroy(); }); req.on('end', () => { try { resolve(JSON.parse(d || '{}')); } catch { resolve({}); } }); }); }
function isAdmin(req) { return req.headers['x-admin-token'] === ADMIN_TOKEN; }

const server = http.createServer(async (req, res) => {
  cors(res);
  if (req.method === 'OPTIONS') return json(res, 204, {});
  const url = new URL(req.url, 'http://localhost');
  
  if (req.method === 'GET' && url.pathname === '/health') {
    return json(res, 200, { status: 'ok', time: new Date().toISOString() });
  }

  const path = url.pathname.replace(/^\/api\/v1/, '');
  if (!url.pathname.startsWith('/api/v1')) {
    if (req.method === 'GET') return serveStatic(req, res, url.pathname);
    return json(res, 404, { error: 'not_found', hint: 'use /api/v1' });
  }

  try {
    if (req.method === 'GET' && path === '/events') return json(res, 200, { data: listEvents() });
    if (req.method === 'GET' && /^\/events\/[^/]+$/.test(path)) { const e = getEvent(decodeURIComponent(path.split('/')[2])); return e ? json(res, 200, { data: e }) : json(res, 404, { error: 'not_found' }); }
    if (req.method === 'GET' && path === '/sessions') return json(res, 200, { data: listSessions(url.searchParams.get('date') || undefined) });
    if (req.method === 'GET' && path === '/portfolio') return json(res, 200, { data: listPortfolio() });

    if (req.method === 'POST' && path === '/admin/upload') {
      // Real file upload for event posters, gallery images, and portfolio
      // images — previously these fields existed on the data model but
      // there was no way to actually get a file onto the server; the admin
      // could only type a path by hand. Accepts a base64 data URL, writes
      // it to disk under assets/uploads/<kind>/, and returns the relative
      // path the same PATCH /admin/events (or /admin/portfolio) endpoints
      // already accept for poster/gallery/video fields.
      if (!isAdmin(req)) return json(res, 401, { error: 'unauthorized' });
      const body = await readBody(req, 15_000_000); // up to ~15MB decoded (images/short clips)
      const { data, filename, kind } = body;
      if (!data || typeof data !== 'string' || !data.startsWith('data:')) {
        return json(res, 400, { error: 'validation', details: 'data must be a base64 data URL' });
      }
      const allowedKinds = ['poster', 'gallery', 'video', 'portfolio'];
      const safeKind = allowedKinds.includes(kind) ? kind : 'gallery';
      const match = data.match(/^data:([^;]+);base64,(.*)$/s);
      if (!match) return json(res, 400, { error: 'validation', details: 'malformed data URL' });
      const [, mime, base64] = match;
      const extMap = { 'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp', 'image/gif': '.gif', 'video/mp4': '.mp4', 'video/webm': '.webm' };
      const ext = extMap[mime] || (filename && filename.includes('.') ? filename.slice(filename.lastIndexOf('.')) : '.bin');
      const safeName = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}${ext}`;
      const uploadDir = join(SITE_ROOT, 'assets', 'uploads', safeKind);
      mkdirSync(uploadDir, { recursive: true });
      writeFileSync(join(uploadDir, safeName), Buffer.from(base64, 'base64'));
      const relPath = `assets/uploads/${safeKind}/${safeName}`;
      return json(res, 201, { data: { path: relPath, kind: safeKind } });
    }

    if (req.method === 'POST' && path === '/admin/events') {
      if (!isAdmin(req)) return json(res, 401, { error: 'unauthorized' });
      const body = await readBody(req);
      const item = { id: 'ev-' + Date.now(), ...body };
      store.set('events', [...store.get('events'), item]);
      return json(res, 201, { data: item });
    }

    if (req.method === 'PATCH' && /^\/admin\/events\/[^/]+$/.test(path)) {
      if (!isAdmin(req)) return json(res, 401, { error: 'unauthorized' });
      const id = path.split('/')[3];
      const body = await readBody(req);
      const events = store.get('events');
      const idx = events.findIndex(e => e.id === id);
      if (idx > -1) {
          events[idx] = { ...events[idx], ...body };
          store.set('events', events);
          return json(res, 200, { data: events[idx] });
      }
      return json(res, 404, { error: 'not_found' });
    }

    if (req.method === 'POST' && path === '/admin/portfolio') {
      if (!isAdmin(req)) return json(res, 401, { error: 'unauthorized' });
      const body = await readBody(req);
      const item = { id: Date.now(), ...body };
      store.set('portfolio', [...store.get('portfolio'), item]);
      return json(res, 201, { data: item });
    }

    if (req.method === 'PATCH' && /^\/admin\/portfolio\/[^/]+$/.test(path)) {
      if (!isAdmin(req)) return json(res, 401, { error: 'unauthorized' });
      const id = Number(path.split('/')[3]);
      const body = await readBody(req);
      const pf = store.get('portfolio');
      const idx = pf.findIndex(p => p.id === id);
      if (idx > -1) {
          pf[idx] = { ...pf[idx], ...body };
          store.set('portfolio', pf);
          return json(res, 200, { data: pf[idx] });
      }
      return json(res, 404, { error: 'not_found' });
    }
    if (req.method === 'GET' && /^\/reservations\/[^/]+$/.test(path)) return json(res, 200, { data: getReservation(path.split('/')[2]) });
    
    if (req.method === 'GET' && path === '/admin/dashboard') {
      if (!isAdmin(req)) return json(res, 401, { error: 'unauthorized' });
      return json(res, 200, { data: getDashboardStats() });
    }
    
    if (req.method === 'GET' && path === '/admin/reservations') {
      if (!isAdmin(req)) return json(res, 401, { error: 'unauthorized' });
      return json(res, 200, { data: listReservations() });
    }

    if (req.method === 'POST' && path === '/admin/sessions') {
      if (!isAdmin(req)) return json(res, 401, { error: 'unauthorized' });
      const body = await readBody(req);
      const session = { id: 's' + Date.now(), ...body, capacity: Number(body.capacity), price: Number(body.price), status: body.status || 'ACTIVE' };
      store.set('sessions', [...store.get('sessions'), session]);
      return json(res, 201, { data: session });
    }

    if (req.method === 'PATCH' && /^\/admin\/sessions\/[^/]+\/status$/.test(path)) {
      if (!isAdmin(req)) return json(res, 401, { error: 'unauthorized' });
      const id = path.split('/')[3];
      const body = await readBody(req);
      const sessions = store.get('sessions');
      const idx = sessions.findIndex(s => s.id === id);
      if (idx > -1) {
          sessions[idx].status = body.status;
          store.set('sessions', sessions);
          return json(res, 200, { data: sessions[idx] });
      }
      return json(res, 404, { error: 'not_found' });
    }

    if (req.method === 'POST' && path === '/reservations') {
      const body = await readBody(req);
      const result = body.waiting_list ? joinWaitingList(body) : reserve(body);
      return result.error ? json(res, result.error === 'sold_out' ? 409 : 400, result) : json(res, 201, result);
    }
    if (req.method === 'POST' && path === '/payments/receipt') {
      const body = await readBody(req);
      const result = uploadReceipt(body.id, body);
      return result.error ? json(res, 400, result) : json(res, 200, result);
    }
    if (req.method === 'PATCH' && /^\/reservations\/[^/]+\/status$/.test(path)) {
      if (!isAdmin(req)) return json(res, 401, { error: 'unauthorized' });
      const result = setStatus(path.split('/')[2], { ...(await readBody(req)), actor: 'admin-web' });
      return result.error ? json(res, 400, result) : json(res, 200, result);
    }
    if (req.method === 'POST' && path === '/auth/login') {
      const body = await readBody(req);
      return json(res, 200, { token: body.token === ADMIN_TOKEN ? 'session-ok' : null });
    }
    return json(res, 404, { error: 'not_found' });
  } catch (err) { return json(res, 500, { error: 'internal', message: String(err) }); }
});

server.listen(PORT, () => console.log(`[mavara] API v1 listening on :${PORT}`));
