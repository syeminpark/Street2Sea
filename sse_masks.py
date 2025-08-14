# sse_masks.py
import json, time, threading, requests

def start_mask_watcher(base_url: str, on_mask_ready):
    def _loop():
        url = base_url.rstrip('/') + '/events'
        last_id = 10**9  # skip existing backlog on the very first connect
        headers = {'Accept': 'text/event-stream'}
        while True:
            try:
                h = dict(headers)
                if last_id:
                    h['Last-Event-ID'] = str(last_id)
                with requests.get(url, stream=True, timeout=60, headers=h) as r:
                    r.raise_for_status()
                    for line in r.iter_lines(decode_unicode=True):
                        if not line:
                            continue
                        if line.startswith('id:'):
                            try:
                                last_id = int(line[3:].strip())
                            except Exception:
                                pass
                            continue
                        if not line.startswith('data:'):
                            continue
                        raw = line[5:].strip()
                        try:
                            evt = json.loads(raw)
                        except Exception:
                            try:
                                evt = json.loads(json.loads(raw))
                            except Exception:
                                continue
                        if isinstance(evt, dict) and evt.get('type') == 'mask-saved':
                            uuid = evt.get('uuid')
                            fname = (evt.get('filename') or "").lower()
                            prof = 'underwater' if 'underwater' in fname else 'overwater'
                            on_mask_ready(uuid, prof)
            except Exception as e:
                print('[SSE] disconnected, retry in 2s:', e)
                time.sleep(2)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return t
