# sse_masks.py
import json
import time
import threading
import requests

def _iter_sse_lines(resp):
    """Yield complete SSE events as dicts {'id':..., 'data': '...'}."""
    event = {'id': None, 'data': []}
    for raw in resp.iter_lines(decode_unicode=True):
        if raw is None:
            continue
        line = raw.strip()

        # blank line -> dispatch current event
        if line == "":
            if event['data']:
                yield {'id': event['id'], 'data': "\n".join(event['data'])}
            event = {'id': None, 'data': []}
            continue

        if line.startswith("id:"):
            event['id'] = line[3:].strip()
        elif line.startswith("data:"):
            event['data'].append(line[5:].strip())
        # ignore other fields

    # flush tail (in case stream ends without blank line)
    if event['data']:
        yield {'id': event['id'], 'data': "\n".join(event['data'])}

def start_mask_watcher(base_url: str, on_mask_ready):
    def _loop():
        url = base_url.rstrip('/') + '/events?replay=0'   # ← no backlog
        headers = {'Accept': 'text/event-stream'}
        while True:
            try:
                with requests.get(url, stream=True, timeout=60, headers=headers) as r:
                    r.raise_for_status()
                    for evt in _iter_sse_lines(r):
                        try:
                            payload = json.loads(evt['data'])
                        except Exception:
                            # some paths might send JSON stringified twice; try once more
                            try:
                                payload = json.loads(json.loads(evt['data']))
                            except Exception:
                                continue
                        if isinstance(payload, dict) and payload.get('type') == 'mask-saved':
                            fname = (payload.get('filename') or "").lower()
                            profile = 'underwater' if 'underwater' in fname else 'overwater'
                            on_mask_ready(payload.get('uuid'), profile)
            except Exception as e:
                print('[SSE] disconnected, retry in 2s:', e)
                time.sleep(2)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return t
