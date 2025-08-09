# app.py

import sys
from PyQt5.QtWidgets import QApplication, QMessageBox
from interface import AddressForm
from googleAPI import addressToCoordinates, getStreetView
from TEJapanAPI import find_and_download_flood_data
from preprocessNCFile import openClosestFile, getNearestValueByCoordinates, buildDepthPatch 
from constants import TEJapanFileType, WebDirectory
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pythonToJS import start_node, sendToNode, wait_health
from saveImages import save_images


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


def handle_form(data):
    try:
        w.ensure_map_started()
        # 1) Build the address
        address = " ".join([
            data["prefecture"],
            data["city"],
            data["town"],
            data["address2"]
        ])
        print(data["timezone"])
        # 2) Geocode
        coords = addressToCoordinates(address)  # e.g. "35.78,139.90"
        print("!!!building coords",coords)
        target_dt=dateConverter(data)

        # 4) Fetch Street‑View
        tiles, metas = getStreetView(
            coords,
            target_date=data["date"],
            mode=data["mode"]
        )
        # Save them into 'images' folder
        UUID = save_images(tiles)
        meta["uuid"]= UUID

        w.set_street_images(tiles, metas)

        for meta in metas:
            meta["type"] = "camera"
        sendToNode(metas, API_URL)

        # 5) Download the best flood data for that datetime
        dt_fetched, resolution = find_and_download_flood_data(target_dt)
    
        # 6) Depth: open closest file before or at target_dt
        ds_depth = openClosestFile(
            TEJapanFileType.DEPTH,
            target_dt
        )

        depth_value, depth_time = getNearestValueByCoordinates(
            ds_depth,
            coords,
            target_dt
        )
        print(depth_value)

        depth_payload = {
            "type"     : "depth",
            "value"    : depth_value,
            "location" : coords,
            "lat"      : metas[0]["lat"],
            "lng"      : metas[0]["lng"],
        }
        sendToNode(depth_payload, API_URL)

    except Exception as e:
        msg = str(e)
        w.log.append(f"⚠ Error: {msg}")
        QMessageBox.warning(w, "Error", msg)


if __name__ == "__main__":
    start_node()
    wait_health(BASE_URL+"/health")

    app = QApplication(sys.argv)
    w = AddressForm()
    w.data_submitted.connect(handle_form)
    w.show()
    sys.exit(app.exec_())
