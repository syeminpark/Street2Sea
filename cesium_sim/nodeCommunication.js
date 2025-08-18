// stream.js (ES module)
let es = null;

export function initNodeStream(viewer, onData) {
  if (!viewer) throw new Error('initNodeStream: pass a Cesium viewer');

  // close any previous connection first
  if (es) { try { es.close(); } catch {} es = null; }

  es = new EventSource('/events');   // don't use a local const; keep it in module scope

  es.onopen = () => console.log('[SSE] open');
  es.onmessage = (ev) => {
    if (!ev.data) return;
    let payload;
    try { payload = JSON.parse(ev.data); } catch { return; }
    try { onData(payload, viewer); } catch (e) { console.error('onData error', e); }
  };
  es.onerror = (e) => console.error('[SSE] error – will auto-reconnect', e);

  // optional: expose for quick inspection in DevTools
  window.__es = es;
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

def wait_for_clients(min_clients: int = 1, timeout_sec: float = 10.0) -> bool:
    try:
        r = requests.post(
            BASE_URL + "/wait-clients",
            params={"min": min_clients, "timeout": int(timeout_sec * 1000)},
            timeout=timeout_sec + 2,
        )
        return r.ok and r.json().get("ok", False)
    except Exception:
        return False