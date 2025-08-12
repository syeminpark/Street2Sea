// server.js  (CommonJS style for consistency)
require('dotenv').config();
const express                = require('express');
const fs                     = require('fs');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();
const PORT = process.env.PORT || 8080;   // fallback to 8080
const HOST = process.env.HOST || 'localhost';
const CAMERA_METADATA_ROUTE= process.env.CAMERA_METADATA_ROUTE || '/api/coords'
const path = require('path');


app.use(express.json({ limit: "25mb" }));           // adjust as needed
// If you ever POST form-data, also raise urlencoded:
app.use(express.urlencoded({ limit: "25mb", extended: true }));

/* ------------------------------------------------------------------ */
/* 1️⃣ Dynamic root: inject your Cesium ion token into index.html      */
app.get('/', (req, res) => {
  const token = JSON.stringify(process.env.CESIUM_ION_TOKEN || '');
  // JSON.stringify adds the quotes, escaping if needed ("eyJhbGci...")
  const html = fs
    .readFileSync('index.template.html', 'utf8')
    .replace("'CESIUM_ION_TOKEN'", token)        // ← replace including the quotes
    .replace('"CESIUM_ION_TOKEN"', token);       // handle double-quoted case too
  res.send(html);
});

app.get('/health', (_, res) => res.send('OK'));
/* ------------------------------------------------------------------ */
/* 2️⃣ Proxy OSM tiles so they appear same‑origin to the browser       */
/*    - We use the generic “tile.openstreetmap.org” host so the       */
/*      proxy works for a/b/c sub‑domains.                            */
/*    - changeOrigin makes the Host header match the target.          */
/*    - pathRewrite strips the /osm prefix before forwarding.         */
/*    - onProxyRes adds CORS headers for completeness (useful         */
/*      if you later serve your app from a different origin).         */
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

/* ------------------------------------------------------------------ */
/* 3️⃣ Static assets: Cesium JS, CSS, your own JS/CSS, etc.            */
app.use(express.static('.'))

const clients = new Set();                     // store open connectionsconst 
const backlog = [];
const BACKLOG_LIMIT = 50;  // keep last 50 messages
let nextEventId = 1;


function enqueue(payload) {
  const evt = {
    id: nextEventId++,
    // keep as already-stringified JSON so we write it directly
    data: typeof payload === 'string' ? payload : JSON.stringify(payload),
    ts: Date.now(),
  };
  backlog.push(evt);
  while (backlog.length > BACKLOG_LIMIT) backlog.shift();
  return evt;
}

function writeEvent(stream, evt) {
  stream.write(`id: ${evt.id}\n`);
  stream.write(`data: ${evt.data}\n\n`);
}


app.get('/events', (req, res) => {
  res.set({
    'Content-Type'           : 'text/event-stream',
    'Cache-Control'          : 'no-cache',
    'Connection'             : 'keep-alive',
    'X-Accel-Buffering'      : 'no' // for nginx, prevents buffering
  });
  res.flushHeaders();
  res.write('\n'); // establish stream

  clients.add(res);

  // 1) immediately replay backlog so we cover the "sent before JS ready" case
  for (const evt of backlog) writeEvent(res, evt);

  // 2) keep the connection alive
  const ping = setInterval(() => res.write(`: ping ${Date.now()}\n\n`), 15000);

  // 3) clean up on close
  req.on('close', () => {
    clearInterval(ping);
    clients.delete(res);
  });
});

app.post(CAMERA_METADATA_ROUTE, (req, res) => {
  const evt = enqueue(req.body);

  let delivered = 0;
  for (const stream of clients) {
    writeEvent(stream, evt);
    delivered++;
  }

  res.json({
    ok: true,
    delivered,
    queued: backlog.length,
    lastEventId: evt.id
  });
});

app.post('/save-mask', (req, res) => {
  try {
    const { dataUrl, filename } = req.body;
    if (!dataUrl || !dataUrl.startsWith('data:image/png;base64,')) {
      return res.status(400).json({ error: 'invalid dataUrl' });
    }
    const b64 = dataUrl.split(',')[1];
    const buf = Buffer.from(b64, 'base64');

    // write into a local folder (ensure it exists)
    const outDir = path.join(__dirname,   '..', 'images');
    if (!fs.existsSync(outDir)) fs.mkdirSync(outDir);

    const safeName = filename && filename.endsWith('.png') ? filename : `mask_${Date.now()}.png`;
    const outPath = path.join(outDir, safeName);
    fs.writeFileSync(outPath, buf);

    res.json({ ok: true, path: outPath, url: `/images/${safeName}` });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: String(e) });
  }
});

// serve the saved files
app.use('/images', express.static('images'));


// npm i puppeteer
const puppeteer = require('puppeteer');

app.post('/find-outdoor-js', async (req, res) => {
  const { lat, lng, target_date, radius = 60, tolerance_m = 12, max_hops = 3 } = req.body || {};
  if (typeof lat !== 'number' || typeof lng !== 'number' || !target_date)
    return res.status(400).json({ error: 'lat, lng, target_date required' });

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
    // Wait for __OUT__ to be set
    const result = await page.waitForFunction('window.__OUT__!==undefined', { timeout: 15000 });
    const pano = await page.evaluate('window.__OUT__');
    if (!pano) return res.status(404).json({ error: 'No outdoor pano on/before target_date' });
    res.json({ ok: true, pano });
  } catch (e) {
    res.status(500).json({ error: String(e) });
  } finally {
    await browser.close();
  }
});

/* ------------------------------------------------------------------ */
/* 4️⃣ Listen last                                                    */
app.listen(PORT, () =>
  console.log(`→ http://${HOST}:${PORT}`)
);
