let es = null;
const cid = (self.crypto && crypto.randomUUID) ? crypto.randomUUID()
                                              : String(Date.now() + Math.random());

export function initNodeStream(viewer, onData) {
  if (!viewer) throw new Error('initNodeStream: pass a Cesium viewer');

  if (es) { try { es.close(); } catch {} es = null; }
  es = new EventSource(`/events?cid=${encodeURIComponent(cid)}&replay=0`);

  es.onopen = () => {
    // viewer + handlers are now attached; mark as READY
    fetch(`/client-ready?cid=${encodeURIComponent(cid)}`, { method: 'POST', keepalive: true });
    console.log('[SSE] open');
  };

  es.onmessage = (ev) => {
    if (!ev.data) return;
    let payload; try { payload = JSON.parse(ev.data); } catch { return; }
    try { onData(payload, viewer); } catch (e) { console.error('onData error', e); }
  };
  es.onerror = (e) => console.error('[SSE] error – will auto-reconnect', e);
}
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



