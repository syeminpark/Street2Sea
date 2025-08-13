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


class UiBus(QObject):
    ai_ready = pyqtSignal(bytes)  # emit bytes to update the right panel

bus = UiBus()

def on_mask_ready(uuid: str):
    if "_naive" in uuid.lower():
        return
    try:
        out_path = generate_from_uuid(uuid, images_dir="images")
        with open(out_path, "rb") as f:
            img_bytes = f.read()
        bus.ai_ready.emit(img_bytes)
        print(f"[AI] Generated {out_path}")
    except Exception as e:
        print("[AI] generation failed:", e)

BASE_URL = f"http://{WebDirectory.HOST.value}:{WebDirectory.PORT.value}"
API_URL  = BASE_URL + WebDirectory.CAMERA_METADATA_ROUTE.value


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
        for meta, s in zip(metas, saved):
            meta["type"] = "camera"
            meta["uuid"] = s["uuid"]
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



if __name__ == "__main__":
    start_node()
    wait_health(BASE_URL+"/health")
    start_mask_watcher(BASE_URL, on_mask_ready)

    app = QApplication(sys.argv)
    w = AddressForm()
    bus.ai_ready.connect(w.display_ai_image)
    w.data_submitted.connect(handle_form)
    w.show()
    sys.exit(app.exec_())
