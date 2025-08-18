// server.js (CommonJS)
require('dotenv').config();

const express = require('express');
const fs = require('fs');
const path = require('path');
const { createProxyMiddleware } = require('http-proxy-middleware');
const puppeteer = require('puppeteer');

const app = express();
const PORT = process.env.PORT || 8000;
const HOST = process.env.HOST || 'localhost';
const CAMERA_METADATA_ROUTE = process.env.CAMERA_METADATA_ROUTE || '/api/coords';

// ------------------------------------------------------------------
// Middleware
// ------------------------------------------------------------------
app.use(express.json({ limit: '25mb' }));
app.use(express.urlencoded({ limit: '25mb', extended: true }));

// Serve saved masks
app.use('/images', express.static(path.join(__dirname, '..', 'images')));

// ------------------------------------------------------------------
// Root: inject Cesium ION token into index.template.html
// ------------------------------------------------------------------
app.get('/', (req, res) => {
  const token = JSON.stringify(process.env.CESIUM_ION_TOKEN || '');
  const html = fs
    .readFileSync('index.template.html', 'utf8')
    .replace("'CESIUM_ION_TOKEN'", token)
    .replace('"CESIUM_ION_TOKEN"', token);
  res.send(html);
});

app.get('/health', (_, res) => res.send('OK'));

// ------------------------------------------------------------------
// Proxy OpenStreetMap tiles to appear same-origin
// ------------------------------------------------------------------
app.use(
  '/osm',
  createProxyMiddleware({
    target: 'https://tile.openstreetmap.org',
    changeOrigin: true,
    pathRewrite: { '^/osm': '' },
    onProxyRes: (proxyRes) => {
      proxyRes.headers['Access-Control-Allow-Origin'] = '*';
    },
  })
);

// ------------------------------------------------------------------
// Static assets (Cesium, JS, CSS, etc.)
// ------------------------------------------------------------------
app.use(express.static('.'));

// ------------------------------------------------------------------
// SSE: live-only stream with optional “viewer ready” gating
// ------------------------------------------------------------------
const clients = new Map();   // cid -> res (SSE response stream)
const readyCids = new Set(); // cids that have called /client-ready
let nextEventId = 1;

// Hold events only while there are zero clients connected.
// This is NOT persistent; it's cleared the moment a client connects.
let pending = [];            // items: { id, data }

// Long-poll waiters for readiness
const waiters = new Set();   // items: { min, minReady, res, t }

function _notifyWaiters() {
  for (const w of Array.from(waiters)) {
    if (clients.size >= w.min && readyCids.size >= w.minReady) {
      clearTimeout(w.t);
      waiters.delete(w);
      try { w.res.json({ ok: true, clients: clients.size, ready: readyCids.size }); } catch {}
    }
  }
}

function broadcast(payload) {
  const id = nextEventId++;
  const data = typeof payload === 'string' ? payload : JSON.stringify(payload);

  if (clients.size === 0) {
    pending.push({ id, data });
    return { id, delivered: 0, queued: pending.length };
  }

  let delivered = 0;
  for (const res of clients.values()) {
    res.write(`id: ${id}\n`);
    res.write(`data: ${data}\n\n`);
    delivered++;
  }
  return { id, delivered, queued: pending.length };
}

// /events: live stream; on first connection, flush pending once and clear it
app.get('/events', (req, res) => {
  const cid = String(req.query.cid || `${Date.now()}-${Math.random().toString(16).slice(2)}`);

  res.set({
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'X-Accel-Buffering': 'no',
  });
  res.flushHeaders();
  res.write('retry: 15000\n\n');

  clients.set(cid, res);
  _notifyWaiters();

  // Flush any events queued while there were no clients
  if (pending.length) {
    for (const evt of pending) {
      res.write(`id: ${evt.id}\n`);
      res.write(`data: ${evt.data}\n\n`);
    }
    pending = []; // clear immediately — no replay after first delivery
  }

  const ping = setInterval(() => res.write(`: ping ${Date.now()}\n\n`), 15000);
  req.on('close', () => {
    clearInterval(ping);
    clients.delete(cid);
    readyCids.delete(cid);
    _notifyWaiters();
  });
});

// Mark this connection's cid as "viewer ready"
app.post('/client-ready', (req, res) => {
  const cid = String(req.query.cid || '');
  if (!cid) return res.status(400).json({ ok: false, error: 'missing cid' });
  if (!clients.has(cid)) return res.status(410).json({ ok: false, error: 'cid not connected' });
  readyCids.add(cid);
  _notifyWaiters();
  res.json({ ok: true, clients: clients.size, ready: readyCids.size });
});

// Long-poll until >=min clients AND >=minReady ready clients (default 1/1)
app.post('/wait', (req, res) => {
  const q = req.query || {};
  const min = Math.max(1, parseInt(q.min, 10) || 1);
  const minReady = Math.max(0, parseInt(q.minReady, 10) || 1);
  const timeoutMs = Math.min(60000, parseInt(q.timeout, 10) || 10000);

  if (clients.size >= min && readyCids.size >= minReady) {
    return res.json({ ok: true, clients: clients.size, ready: readyCids.size });
  }

  const t = setTimeout(() => {
    waiters.delete(entry);
    res.status(408).json({ ok: false, timeout: true, clients: clients.size, ready: readyCids.size });
  }, timeoutMs);

  const entry = { min, minReady, res, t };
  waiters.add(entry);
  req.on('close', () => { clearTimeout(t); waiters.delete(entry); });
});

// Back-compat: long-poll until >=min clients (ignores readiness)
app.post('/wait-clients', (req, res) => {
  const q = req.query || {};
  const min = Math.max(1, parseInt(q.min, 10) || 1);
  const timeoutMs = Math.min(60000, parseInt(q.timeout, 10) || 10000);

  if (clients.size >= min) return res.json({ ok: true, clients: clients.size });

  const t = setTimeout(() => {
    waiters.delete(entry);
    res.status(408).json({ ok: false, timeout: true, clients: clients.size });
  }, timeoutMs);

  const entry = { min, minReady: 0, res, t };
  waiters.add(entry);
  req.on('close', () => { clearTimeout(t); waiters.delete(entry); });
});

// Quick probe
app.get('/clients', (_, res) => res.json({ clients: clients.size, ready: readyCids.size }));

// ------------------------------------------------------------------
// API that Python posts to (camera metas / depth)
// ------------------------------------------------------------------
app.post(CAMERA_METADATA_ROUTE, (req, res) => {
  const { id, delivered, queued } = broadcast(req.body);
  res.json({ ok: true, delivered, queued, lastEventId: id });
});

// ------------------------------------------------------------------
// Save mask + notify live listeners (still no backlog)
// ------------------------------------------------------------------
app.post('/save-mask', (req, res) => {
  try {
    const { dataUrl, filename } = req.body;
    if (!dataUrl || !dataUrl.startsWith('data:image/png;base64,')) {
      return res.status(400).json({ error: 'invalid dataUrl' });
    }
    const b64 = dataUrl.split(',')[1];
    const buf = Buffer.from(b64, 'base64');

    const outDir = path.join(__dirname, '..', 'images');
    if (!fs.existsSync(outDir)) fs.mkdirSync(outDir);

    const safeName = filename && filename.endsWith('.png') ? filename : `mask_${Date.now()}.png`;
    const outPath  = path.join(outDir, safeName);
    fs.writeFileSync(outPath, buf);

    // Notify JS/Python listeners
    const m = safeName.match(/^(.+?)_(?:overwater|underwater)_mask\.png$/);
    if (m) {
      broadcast({ type: 'mask-saved', uuid: m[1], filename: safeName, url: `/images/${safeName}` });
    }

    res.json({ ok: true, path: outPath, url: `/images/${safeName}` });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: String(e) });
  }
});

// ------------------------------------------------------------------
// Puppeteer helper (unchanged behavior)
// ------------------------------------------------------------------
app.post('/find-outdoor-js', async (req, res) => {
  const { lat, lng, target_date, radius = 60, tolerance_m = 12, max_hops = 3 } = req.body || {};
  if (typeof lat !== 'number' || typeof lng !== 'number' || !target_date) {
    return res.status(400).json({ error: 'lat, lng, target_date required' });
  }

  const html = `
<!doctype html><html><body>
<div id="app"></div>
<script src="https://maps.googleapis.com/maps/api/js?key=${process.env.GOOGLE_STREET_VIEW_API_KEY}"></script>
<script>
  (async () => {
    const toDate = (s) => { const m = /^([0-9]{4})(?:-([0-9]{2}))?/.exec(s); return m ? new Date(+m[1], (m[2]?+m[2]:1)-1, 1) : null; };
    const targetDate = toDate(${JSON.stringify(target_date)});
    const sv = new google.maps.StreetViewService();
    const origin = new google.maps.LatLng(${lat}, ${lng});
    function getPanorama(req){ return new Promise(r=>sv.getPanorama(req,(d,s)=>r(s==='OK'?d:null))); }
    const seed = await getPanorama({ location: origin, radius: ${radius}, preference: 'nearest', source: google.maps.StreetViewSource.OUTDOOR });
    if (!seed) return window.__OUT__ = null;

    const q = [{data: seed, depth: 0}], seen = new Set([seed.location.pano]);
    let best = null, nearest = 1/0;
    function dateOK(d){ const dt = toDate(d); return dt && dt <= targetDate ? dt : null; }
    const dist = (a,b)=>{ const R=6371000, rd=x=>x*Math.PI/180;
      const dφ=rd(b.lat()-a.lat()), dλ=rd(b.lng()-a.lng()), φ1=rd(a.lat()), φ2=rd(b.lat());
      const x=Math.sin(dφ/2)**2 + Math.cos(φ1)*Math.cos(φ2)*Math.sin(dλ/2)**2;
      return 2*R*Math.atan2(Math.sqrt(x), Math.sqrt(1-x)); };

    while(q.length){
      const {data, depth} = q.shift();
      const ll = data.location.latLng;
      const d = dist(origin, ll);
      const dt = dateOK(data.imageDate);
      if (dt){
        if (d < nearest) nearest = d;
        if (d <= nearest + ${tolerance_m}){
          if (!best || dt > best.dt || (dt.getTime()===best.dt.getTime() && d < best.d)){
            best = { pid: data.location.pano, dt, d, ll };
          }
        }
      }
      if (depth >= ${max_hops}) continue;
      for (const link of (data.links||[])){
        const pid = link.pano; if (!pid || seen.has(pid)) continue; seen.add(pid);
        const next = await getPanorama({ pano: pid }); if (next) q.push({data: next, depth: depth+1});
      }
    }
    window.__OUT__ = best ? { pano_id: best.pid, date: best.dt.toISOString().slice(0,7), lat: best.ll.lat(), lng: best.ll.lng() } : null;
  })();
</script>
</body></html>`.trim();

  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
  try {
    const page = await browser.newPage();
    await page.setContent(html, { waitUntil: 'load' });
    await page.waitForFunction('window.__OUT__!==undefined', { timeout: 15000 });
    const pano = await page.evaluate('window.__OUT__');
    if (!pano) return res.status(404).json({ error: 'No outdoor pano on/before target_date' });
    res.json({ ok: true, pano });
  } catch (e) {
    res.status(500).json({ error: String(e) });
  } finally {
    await browser.close();
  }
});

// ------------------------------------------------------------------
// Graceful shutdown (explicit endpoint + signals)
// ------------------------------------------------------------------
app.post('/shutdown', (req, res) => {
  res.json({ ok: true });
  setTimeout(() => {
    for (const r of clients.values()) { try { r.end(); } catch (_) {} }
    server.close(() => process.exit(0));
  }, 10);
});

process.on('SIGTERM', () => {
  for (const r of clients.values()) { try { r.end(); } catch (_) {} }
  server.close(() => process.exit(0));
});
process.on('SIGINT', () => {
  for (const r of clients.values()) { try { r.end(); } catch (_) {} }
  server.close(() => process.exit(0));
});

// ------------------------------------------------------------------
// Start
// ------------------------------------------------------------------
const server = app.listen(PORT, () =>
  console.log(`→ http://${HOST}:${PORT}`)
);
