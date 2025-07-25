# app.py
import sys
from PyQt5.QtWidgets import QApplication, QMessageBox
from interface import AddressForm
from googleAPI import addressToCoordinates, getStreetView
from constants import PerspectiveMode

def handle_form(data):
    try:
        # 1) Build full address
        address = " ".join([
            data["prefecture"],
            data["city"],
            data["town"],
            data["address2"]
        ])

        # 2) Geocode
        coords = addressToCoordinates(address)
        tiles,metas = getStreetView(coords, target_date= data["date"].split()[0], mode=data["mode"])
        w.set_street_images(tiles,metas,)

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


