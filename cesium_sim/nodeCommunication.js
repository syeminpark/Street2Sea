let es = null;

export function initNodeStream(viewer, onData) {
  if (!viewer) throw new Error('initNodeStream: pass a Cesium viewer');
  const src = new EventSource('/events?replay=0');   // ← ensure no replay
  src.onmessage = (ev) => {
    if (!ev.data) return;
    let payload;
    try { payload = JSON.parse(ev.data); } catch { return; }
    try { onData(payload, viewer); } catch (e) { console.error('onData error', e); }
  };
  src.onerror = (e) => console.error('SSE error – will auto-reconnect', e);
}
// optional helper if you ever need to stop listening manually
export function closeNodeStream() {
  try { es && es.close(); } catch {}
  es = null;
}

export async function sendCanvasAsPNG(canvas, filename = "debug_mask.png") {
  const dataUrl = canvas.toDataURL("image/png");
  const resp = await fetch("/save-mask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataUrl, filename })
  });
  if (!resp.ok) throw new Error(`save-mask ${resp.status}`);
  return resp.json();
}
