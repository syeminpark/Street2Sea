# sse_masks.py
import json
import time
import threading
import requests
from PyQt5.QtWidgets import QApplication
from imageGen import generate_from_uuid, _normalize_uuid
from collections import OrderedDict
from utility import _get_raw_info,_split_prompts

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


_recent = OrderedDict()

def _seen(key, maxlen=200):
    if key in _recent:
        return True
    _recent[key] = None
    if len(_recent) > maxlen:
        _recent.popitem(last=False)
    return False

def on_mask_ready(uuid: str, profile: str = "underwater",ACTIVE_UUIDS=None,bus=None):
    if "_naive" in (uuid or "").lower():
        return
    if QApplication.instance() is None or bus is None:
        return

    try:
        uuid = _normalize_uuid(uuid)
    except Exception:
        pass

    if uuid not in ACTIVE_UUIDS:
        print(f"[SSE] ignoring stale mask for uuid={uuid}")
        return

    if _seen((uuid, profile)):
        return

    bus.tiles_ready.emit()

    try:
        bus.progress.emit("\nGenerating AI image…")
        out_path, infotext = generate_from_uuid(
            uuid, images_dir="images", profile=profile, want_info=True
        )
        with open(out_path, "rb") as f:
            img_bytes = f.read()
        bus.ai_ready.emit(img_bytes)

        if infotext:
            raw = _get_raw_info(infotext)
            pos, neg = _split_prompts(raw)
            bus.progress.emit("[Prompt]")
            if pos:
                bus.progress.emit(f"Positive: {pos}\n")
            if neg:
                bus.progress.emit(f"Negative: {neg}")

        print(f"[AI] Generated {out_path} ({profile})")
    except Exception as e:
        bus.progress.emit(f"[AI] generation failed: {e}")
        print("[AI] generation failed:", e)

