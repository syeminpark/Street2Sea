# app.py

import sys
import json
import os
import threading
from collections import OrderedDict
from datetime import datetime, timezone, timedelta

from PyQt5.QtCore import QTimer, QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMessageBox

from interface import AddressForm
from googleAPI import addressToCoordinates, getStreetView
from TEJapanAPI import find_and_download_flood_data
from preprocessNCFile import (
    openClosestFile,
    getNearestValueByCoordinates,
    buildDepthPatch,
)
from constants import TEJapanFileType, WebDirectory
from zoneinfo import ZoneInfo

from pythonToJS import start_node, sendToNode, wait_health, wait_for_ready
from imageUtility import save_images
from imageGen import generate_from_uuid, _normalize_uuid
from sse_masks import start_mask_watcher
import re


# --------------------------- helpers ---------------------------



JST = ZoneInfo("Asia/Tokyo")
UTC = timezone.utc

def _ensure_aware(dt, assume_tz=UTC):
    """Return an aware datetime. If dt is naive, attach assume_tz."""
    if not isinstance(dt, datetime):
        return dt
    if dt.tzinfo is None:
        return dt.replace(tzinfo=assume_tz)
    return dt

def _to_jst(dt):
    """Convert any datetime (naive→assume UTC) to JST."""
    if not isinstance(dt, datetime):
        return dt
    return _ensure_aware(dt, UTC).astimezone(JST)

def _fmt_dt(dt, tz="JST", fmt="%Y-%m-%d %H:%M"):
    """Format a datetime in JST (default) or UTC ('UTC')."""
    if not isinstance(dt, datetime):
        return str(dt)
    if tz.upper() == "JST":
        return _to_jst(dt).strftime(fmt)
    elif tz.upper() == "UTC":
        return _ensure_aware(dt, UTC).astimezone(UTC).strftime(fmt)
    else:
        return _ensure_aware(dt, UTC).astimezone(ZoneInfo(tz)).strftime(fmt)

def _human_hours(td: timedelta | None) -> str:
    if td is None:
        return "n/a"
    secs = td.total_seconds()
    sign = "-" if secs < 0 else ""
    h = abs(secs) / 3600.0
    return f"{sign}{h:.2f} h"

def _get_raw_info(info):
    """Safely extract a raw prompt string from diverse shapes."""
    if isinstance(info, dict) and "raw" in info:
        return info["raw"]
    raw = getattr(info, "raw", None)
    if isinstance(raw, str):
        return raw
    return str(info)


def _split_prompts(raw: str):
    """
    From a Stable Diffusion-style 'raw' infotext, return (positive, negative)
    and strip trailing metadata (Steps/Sampler/Size/Model/VAE/ControlNet/Refiner/Version...).
    """
    if not isinstance(raw, str):
        return str(raw), ""

    # Find "Negative prompt:" marker (case-insensitive)
    m = re.search(r'(?i)\bnegative\s*prompt\s*:\s*', raw)
    if not m:
        # No explicit negative section; return everything as positive
        pos = raw.strip().rstrip(", ")
        return pos, ""

    pos = raw[:m.start()].strip().rstrip(", ")
    rest = raw[m.end():]

    # Any line that *starts* with a known metadata key ends the negative prompt
    meta_pat = re.compile(
        r'\n\s*(?:'
        r'Steps|Sampler|Schedule type|CFG scale|Seed|Size|Model(?: hash)?|'
        r'VAE(?: hash)?|Denoising strength|Masked content|'
        r'Soft inpainting(?:.*)?|ControlNet\s*\d*|Refiner(?:.*)?|'
        r'Refiner switch at|Version'
        r')\s*:',
        re.IGNORECASE | re.DOTALL
    )
    mm = meta_pat.search(rest)
    neg = (rest[:mm.start()] if mm else rest).strip().rstrip(", ")

    return pos, neg

# --------------------------- global state ---------------------------

_recent = OrderedDict()
ACTIVE_UUIDS = set()

def _seen(key, maxlen=200):
    if key in _recent:
        return True
    _recent[key] = None
    if len(_recent) > maxlen:
        _recent.popitem(last=False)
    return False

BASE_URL = f"http://{WebDirectory.HOST.value}:{WebDirectory.PORT.value}"
API_URL  = BASE_URL + WebDirectory.CAMERA_METADATA_ROUTE.value


class UiBus(QObject):
    ai_ready   = pyqtSignal(bytes)   # bytes for the right panel
    tiles_ready = pyqtSignal()
    progress   = pyqtSignal(str)     # log text lines

bus = None

# --------------------------- network send with readiness wait ---------------------------

def _wait_and_send(payload, label="payload"):
    ok = wait_for_ready(min_clients=1, min_ready=1, timeout_sec=30)
    if ok:
        bus.progress.emit(f"✅ Viewer ready; sending {label}.")
    else:
        bus.progress.emit(f"⚠ Viewer not ready; sending {label} anyway (may be missed without replay).")
    try:
        sendToNode(payload, API_URL)
    except Exception as e:
        bus.progress.emit(f"POST failed for {label}: {e}")

# --------------------------- SSE mask callback ---------------------------

def on_mask_ready(uuid: str, profile: str = "underwater"):
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

# --------------------------- time conversion ---------------------------

def dateConverter(data):
    """
    Parse the user's date/time and return BOTH:
      - target_dt_utc_naive: datetime (naive) interpreted as UTC (for existing pipelines)
      - target_dt_jst:       datetime (aware) in JST (for logging)
    Behavior:
      * If user selected "JST", interpret the input as JST and convert to UTC.
      * If user selected "UTC", interpret input as UTC.
    """
    dt_str = f"{data['date']} {data['time']}"
    naive = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")  # naive user input

    if str(data.get("timezone", "")).upper().startswith("JST"):
        local_jst = naive.replace(tzinfo=JST)
        utc_aware = local_jst.astimezone(UTC)
    else:
        utc_aware = naive.replace(tzinfo=UTC)  # treat input as UTC

    target_dt_utc_naive = utc_aware.replace(tzinfo=None)
    target_dt_jst = utc_aware.astimezone(JST)
    return target_dt_utc_naive, target_dt_jst

# --------------------------- form handling ---------------------------

def handle_form(data):
    print('submit')
    try:
        # 1) Build the address
        address = " ".join([data["prefecture"], data["city"], data["town"], data["address2"]])

        # 2) Geocode
        coords = addressToCoordinates(address)

        # 3) Time conversion
        target_dt_utc, target_dt_jst = dateConverter(data)

        # 4) Fetch Street-View
        tiles, metas = getStreetView(
            coords,
            target_date=data["date"],
            mode=data["mode"],
            tolerance_m=3,
            width=640,
            height=640,
        )
        saved = save_images(tiles)
        ACTIVE_UUIDS.clear()

        for meta, s in zip(metas, saved):
            meta["type"] = "camera"
            meta["uuid"] = s["uuid"]
            ACTIVE_UUIDS.add(s["uuid"])

        w.set_street_images(tiles, metas)
        w.ensure_map_started()

        w.log.append("\n[Street-View Metadata]")
        def _num(val, places=0):
            try: return f"{float(val):.{places}f}"
            except Exception: return "n/a"
        def _num6(val):
            try: return f"{float(val):.6f}"
            except Exception: return "n/a"

        for i, m in enumerate(metas, 1):
            cam_lat  = m.get("lat")
            cam_lng  = m.get("lng")
            pitch    = m.get("pitch")
            heading  = m.get("heading")
            fov      = m.get("fov")
            size     = m.get("size")
            address  = m.get("location")      # this is your "address coords" string
            dist_m   = m.get("distance_m")    # added in googleapi.py

            w.log.append(
                f"Camera latitude/longitude: {_num6(cam_lat)}, {_num6(cam_lng)}\n"
                f"Heading: {_num(heading,0)}°\n"
                f"Pottch: {_num(pitch,0)}°\n"
                f"FOV: {_num(fov,0)}\n"
                f"Dimension: {size}\n"
                f"Address latitude/longitude: {address}\n"
                f"Distance Between Camera and Address: {_num(dist_m,1)} m\n"
            )

        # Send camera metas (non-blocking, waits for viewer readiness)
        threading.Thread(target=_wait_and_send, args=(metas, "Street-View metadata"), daemon=True).start()

        # 5) Depth
        if data.get("depth_override_enabled"):
            depth_value = float(data.get("depth_override_value", 0.0))
            w.log.append(f"✔ Using depth override = {depth_value:.2f} m (skipping TE-Japan).")
            dt_fetched = None
            depth_time = None
            resolution = "override"
        else:
            dt_fetched, resolution = find_and_download_flood_data(target_dt_utc)
            ds_depth = openClosestFile(TEJapanFileType.DEPTH, target_dt_utc)
            depth_value, depth_time = getNearestValueByCoordinates(ds_depth, coords, target_dt_utc)

        # Lead time (use aware UTC for subtraction)
        lead_td = None
        try:
            lead_td = _ensure_aware(target_dt_utc, UTC) - _ensure_aware(dt_fetched, UTC) if dt_fetched else None
        except Exception:
            lead_td = None

        # 5b) Log one line at a time — in JST
        w.log.append("\n[TE-JAPAN DATA]")
        if resolution: w.log.append(f"Resolution: {resolution}")
        if lead_td is not None:
            w.log.append(f"Lead time: {_human_hours(lead_td)}")
        if dt_fetched:
            w.log.append(f"Model run: {_fmt_dt(dt_fetched, 'JST')} (JST)")
        if depth_value is not None and depth_time is not None:
            w.log.append(f"Flood depth: {float(depth_value):.2f} m @ {_fmt_dt(depth_time, 'JST')} (JST)\n")
      

        # 6) Send depth to the browser
        depth_payload = {
            "type": "depth",
            "value": float(depth_value),
            "location": coords,
            "lat": metas[0]["lat"],
            "lng": metas[0]["lng"],
            "size": metas[0]["size"],
        }
        threading.Thread(target=_wait_and_send, args=(depth_payload, "flood depth"), daemon=True).start()

    except Exception as e:
        msg = str(e)
        w.log.append(f"⚠ Error: {msg}")
        QMessageBox.warning(w, "Error", msg)

# --------------------------- main ---------------------------

if __name__ == "__main__":
    start_node()
    wait_health(BASE_URL + "/health")

    app = QApplication(sys.argv)

    bus = UiBus()  # create after QApp
    w = AddressForm()

    from PyQt5.QtCore import Qt
    bus.ai_ready.connect(w.display_ai_image, type=Qt.QueuedConnection)
    bus.tiles_ready.connect(w.on_tiles_ready, type=Qt.QueuedConnection)
    bus.progress.connect(w.log.append, type=Qt.QueuedConnection)
    w.data_submitted.connect(handle_form)

    def _start_sse():
        global mask_thread
        mask_thread = start_mask_watcher(BASE_URL, on_mask_ready)

    QTimer.singleShot(0, _start_sse)   # schedule once UI is up

    w.show()
    sys.exit(app.exec_())
