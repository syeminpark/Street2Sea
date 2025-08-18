# app.py

import sys
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal
from interface import AddressForm
from googleAPI import addressToCoordinates, getStreetView
from TEJapanAPI import find_and_download_flood_data
from preprocessNCFile import openClosestFile, getNearestValueByCoordinates, buildDepthPatch 
from constants import TEJapanFileType, WebDirectory
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pythonToJS import start_node, sendToNode, wait_health
from imageUtility import save_images
from imageGen import generate_from_uuid
import threading, json, os
from sse_masks import start_mask_watcher
from imageGen import _normalize_uuid
from collections import OrderedDict
from PyQt5.QtCore import QTimer


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
    ai_ready = pyqtSignal(bytes)  # emit bytes to update the right panel
    tiles_ready = pyqtSignal() 
    progress   = pyqtSignal(str)   # <-- NEW
    

bus = None

def on_mask_ready(uuid: str, profile: str = "underwater"):
    if "_naive" in uuid.lower():
        return
    if QApplication.instance() is None or bus is None:
        return

    # normalize and ignore if it’s not from this run
    try:
        from imageGen import _normalize_uuid
        uuid = _normalize_uuid(uuid)
    except Exception:
        pass

    if uuid not in ACTIVE_UUIDS:
        print(f"[SSE] ignoring stale mask for uuid={uuid}")
        return

    # (optional) per-run de-dupe
    if _seen((uuid, profile)):
        return

    bus.tiles_ready.emit()

    try:
        out_path, infotext = generate_from_uuid(uuid, images_dir="images",
                                                profile=profile, want_info=True)
        with open(out_path, "rb") as f:
            img_bytes = f.read()
        bus.ai_ready.emit(img_bytes)
        if infotext:
            bus.progress.emit(infotext)
        print(f"[AI] Generated {out_path} ({profile})")
    except Exception as e:
        bus.progress.emit(f"[AI] generation failed: {e}")
        print("[AI] generation failed:", e)


def dateConverter(data):
     # 3) Parse date+hour into a full datetime
        dt_str = f"{data['date']} {data['time']}"
        # parse into a naive datetime
        naive = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        # attach tzinfo based on the user’s selection, then convert to UTC
        if data["timezone"].startswith("JST"):
            local = naive.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
            target_dt = local.astimezone(timezone.utc).replace(tzinfo=None)
            print("UTC:", target_dt)
        else:
            # assume it’s already UTC
            target_dt = naive
        return target_dt


# app.py
def handle_form(data):
    print('submit')
    try:
        # 1) Build the address (unchanged)
        address = " ".join([data["prefecture"], data["city"], data["town"], data["address2"]])

        # 2) Geocode
        coords = addressToCoordinates(address)

        # 3) Time zone conversion (still useful for logs/consistency)
        target_dt = dateConverter(data)
    

        # 4) Fetch Street-View (unchanged)
        tiles, metas = getStreetView(
            coords,
            target_date=data["date"],
            mode=data["mode"],
            tolerance_m=3,
            width=640,
            height=640,
        )
        saved = save_images(tiles)
        w.set_street_images(tiles, metas)
        
        w.ensure_map_started()
        ACTIVE_UUIDS.clear()

        for meta, s in zip(metas, saved):
            meta["type"] = "camera"
            meta["uuid"] = s["uuid"]
            ACTIVE_UUIDS.add(s["uuid"])
        sendToNode(metas, API_URL)



        # NEW 5) Depth: use override if provided
        if data.get("depth_override_enabled"):
            depth_value = float(data.get("depth_override_value", 0.0))
            w.log.append(f"✔ Using depth override = {depth_value:.2f} m (skipping TE-Japan).")
        else:
            # Old flow (download + open + sample)
            dt_fetched, resolution = find_and_download_flood_data(target_dt)
            ds_depth = openClosestFile(TEJapanFileType.DEPTH, target_dt)
            depth_value, depth_time = getNearestValueByCoordinates(ds_depth, coords, target_dt)
        print(data.get("depth_override_enabled"),depth_value)

        # 6) Send depth to the browser (JS will use payload.value)
        depth_payload = {
            "type": "depth",
            "value": float(depth_value),
            "location": coords,
            "lat": metas[0]["lat"],
            "lng": metas[0]["lng"],
            "size": metas[0]["size"],
        }
        sendToNode(depth_payload, API_URL)

    except Exception as e:
        msg = str(e)
        w.log.append(f"⚠ Error: {msg}")
        QMessageBox.warning(w, "Error", msg)

# app.py (bottom)
if __name__ == "__main__":
    start_node()
    wait_health(BASE_URL + "/health")

    app = QApplication(sys.argv)

    bus = UiBus()  # create after QApp
    w = AddressForm()

    from PyQt5.QtCore import Qt
    bus.ai_ready.connect(w.display_ai_image, type=Qt.QueuedConnection)
    bus.tiles_ready.connect(w.on_tiles_ready, type=Qt.QueuedConnection)
    bus.progress.connect(w.log.append, type=Qt.QueuedConnection)   # <-- NEW
    w.data_submitted.connect(handle_form)
    

    def _start_sse():
        global mask_thread
        mask_thread = start_mask_watcher(BASE_URL, on_mask_ready)

    QTimer.singleShot(0, _start_sse)   # schedule once UI is up

    w.show()
    sys.exit(app.exec_())
