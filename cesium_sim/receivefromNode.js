export function initNodeStream(viewer, onData) {
  if (!viewer) throw new Error('initNodeStream: pass a Cesium viewer');

  const src = new EventSource('/events');

  src.onmessage = (ev) => {
    if (!ev.data) return;                 // ignore heartbeat lines
    let payload;
    try { payload = JSON.parse(ev.data); }
    catch { return console.warn('SSE: bad JSON', ev.data); }

    try { onData(payload, viewer); }
    catch (e) { console.error('onData error', e); }
  };

  src.onerror = (e) => console.error('SSE error – will auto-reconnect', e);
}
