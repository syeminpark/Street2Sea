# app.py
import sys
from PyQt5.QtWidgets import QApplication, QMessageBox
from interface import AddressForm
from googleAPI import addressToCoordinates, getStreetView
from TEJapanAPI import find_and_download_flood_data
from preprocessNCFile import openClosestFile, getNearestValueByCoordinates, floodVolumeProxy
from constants import TEJapanFileType
from datetime import datetime

def handle_form(data):
    try:
        # 1) Build the address
        address = " ".join([
            data["prefecture"],
            data["city"],
            data["town"],
            data["address2"]
        ])

        # 2) Geocode
        coords = addressToCoordinates(address)

        # 3) Parse date string into a datetime.date (00:00:00)
        #    data["date"] is something like "2025‑07‑25"
        target_dt = datetime.fromisoformat(data["date"])

        # 4) Fetch street view
        tiles, metas = getStreetView(
            coords,
            target_date=data["date"],  # still pass the string here if that API expects it
            mode=data["mode"]
        )
        w.set_street_images(tiles, metas)

        # 5) Download flood data
        find_and_download_flood_data(target_dt)
        # 6) Open the closest .nc file BEFORE (or at) our datetime
        #    Note the swapped argument order: (fileType, target_datetime)

        # w.log.append
        dataset = openClosestFile(
            TEJapanFileType.DEPTH.value,
            target_dt
        )
        print(coords)
        # 7) Extract the nearest value at our coords
        flood_val = getNearestValueByCoordinates(dataset, coords,target_dt)
        w.log.append(f"Dataset: {dataset}")
    
        w.log.append(f"🌊 Flood value at location: {flood_val}")


    except Exception as e:
        err = str(e)
        w.log.append(f"⚠ Error: {err}")
        QMessageBox.warning(w, "API Error", err)
 
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = AddressForm()
    w.data_submitted.connect(handle_form)
    w.show()
    sys.exit(app.exec_())

