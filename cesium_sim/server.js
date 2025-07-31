// server.js  (CommonJS style for consistency)
require('dotenv').config();
const express                = require('express');
const fs                     = require('fs');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();
const PORT = process.env.PORT || 8080;   // fallback to 8080
const HOST = process.env.HOST || 'localhost';
const CAMERA_METADATA_ROUTE= process.env.CAMERA_METADATA_ROUTE || '/api/coords'

app.use(express.json());  

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

const clients = new Set();                     // store open connections

app.get('/events', (req, res) => {             // •••
  res.set({                                   // headers required by SSE
    'Content-Type' : 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection     : 'keep-alive'
  });
  res.flushHeaders();                          // send headers immediately
  res.write('\n');                             // 1st blank line = ok

  clients.add(res);                            // keep track
  req.on('close', () => clients.delete(res));  // remove when tab closes
});


app.post(CAMERA_METADATA_ROUTE, (req, res) => {
  const payload = JSON.stringify(req.body);

  // broadcast to every connected browser
  for (const stream of clients) {
    stream.write(`data: ${payload}\n\n`);
  }

  res.json({ status: 'ok', sentTo: clients.size });
});


/* ------------------------------------------------------------------ */
/* 4️⃣ Listen last                                                    */
app.listen(PORT, () =>
  console.log(`→ http://${HOST}:${PORT}`)
);



