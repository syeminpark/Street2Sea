# app.py
import sys
from PyQt5.QtWidgets import QApplication, QMessageBox
from interface import AddressForm
from googleAPI import addressToCoordinates, getStreetViewByDate, getPanoramaByDateTiles

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

        # 3) Fetch the 3×120° tiles
        tiles,metas = getPanoramaByDateTiles(coords, target_date= data["date"].split()[0])

        # 4) Hand off to your UI for Prev/Next navigation
        w.set_street_images(tiles,metas)

        # 5) (…and similarly AI image…)
        # ai_resp = getAIImage(coords)
        # w.display_ai_image(ai_resp.content)

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
