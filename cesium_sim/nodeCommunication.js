
export function initNodeStream(viewer, onData) {
  if (!viewer) throw new Error('initNodeStream: pass a Cesium viewer');
  const src = new EventSource('/events');
  src.onmessage = (ev) => {
    if (!ev.data) return;
    let payload;
    try { payload = JSON.parse(ev.data); } catch { return; }
    try { onData(payload, viewer); } catch (e) { console.error('onData error', e); }
  };
  src.onerror = (e) => console.error('SSE error – will auto-reconnect', e);
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

