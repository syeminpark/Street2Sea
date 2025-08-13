# sse_masks.py
import json, time, threading, requests

def start_mask_watcher(base_url: str, on_mask_ready):
    """
    Opens one SSE stream to <base_url>/events and calls on_mask_ready(uuid)
    whenever Node announces a new mask.
    """
    def _loop():
        url = base_url.rstrip('/') + '/events'
        while True:
            try:
                with requests.get(url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    for line in r.iter_lines(decode_unicode=True):
                        if not line:
                            continue
                        if line.startswith('data:'):
                            raw = line[5:].strip()
                            # backlog items may already be JSON strings
                            try:
                                evt = json.loads(raw)
                            except Exception:
                                try:
                                    evt = json.loads(json.loads(raw))
                                except Exception:
                                    continue
                            if isinstance(evt, dict) and evt.get('type') == 'mask-saved':
                                uuid = evt.get('uuid')
                                if uuid:
                                    on_mask_ready(uuid)
            except Exception as e:
                print('[SSE] disconnected, retry in 2s:', e)
                time.sleep(2)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return t
