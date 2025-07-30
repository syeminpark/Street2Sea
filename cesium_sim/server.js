// server.js  (CommonJS style for consistency)
require('dotenv').config();
const express                = require('express');
const fs                     = require('fs');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();

console.log('Loaded CESIUM_ION_TOKEN =', process.env.CESIUM_ION_TOKEN);

/* ------------------------------------------------------------------ */
/* 1️⃣ Dynamic root: inject your Cesium ion token into index.html      */
app.get('/', (req, res) => {
  const html = fs
    .readFileSync('index.template.html', 'utf8')
    .replace('CESIUM_ION_TOKEN', process.env.CESIUM_ION_TOKEN || '');
  res.send(html);
});

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
app.use(express.static('.'));

/* ------------------------------------------------------------------ */
/* 4️⃣ Listen last                                                    */
app.listen(8000, () => console.log('→ http://localhost:8000'));
