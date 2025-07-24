# interface.py
import json
from PyQt5.QtCore import QUrl, pyqtSignal, QByteArray
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
from interface_ui import AddressFormUI

class AddressForm(AddressFormUI):

    data_submitted = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

        # connect signals
        self.postal.editingFinished.connect(self.lookup_postal)
        self.postal.textChanged.connect(self.update_submit_state)
        self.address2.textChanged.connect(self.update_submit_state)
        self.submit_btn.clicked.connect(self._on_submit)

        # postal lookup manager
        self.net = QNetworkAccessManager(self)
        self.net.finished.connect(self._on_api_response)

        # initialize button state
        self.update_submit_state()

    def update_submit_state(self):
        """
        Enable Submit only when both Postal Code and Address Line 2 are non‑empty.
        """
        has_postal = bool(self.postal.text().strip())
        has_addr2  = bool(self.address2.text().strip())
        self.submit_btn.setEnabled(has_postal and has_addr2)

    def lookup_postal(self):
        code = self.postal.text().strip().replace("-", "")
        if len(code) != 7 or not code.isdigit():
            return
        self.log.append(f"Looking up postal code {code}…")
        url = QUrl(f"https://zipcloud.ibsnet.co.jp/api/search?zipcode={code}")
        self.net.get(QNetworkRequest(url))

    def _on_api_response(self, reply):
        if reply.error():
            err = reply.errorString()
            self.log.append(f"Lookup failed: {err}")
            return

        data = json.loads(bytes(reply.readAll()).decode())
        if data.get("status") != 200 or not data.get("results"):
            self.log.append("No address found for that postal code.")
            return

        r = data["results"][0]
        # populate fields
        self.prefecture  .setText(r["address1"])
        self.city        .setText(r["address2"])
        self.town        .setText(r["address3"])
        self.prefecture_en.setText(self.converter.do(r["address1"]))
        self.city_en      .setText(self.converter.do(r["address2"]))
        self.town_en      .setText(self.converter.do(r["address3"]))
        self.log.append(
            f"Address found: {r['address1']} {r['address2']} {r['address3']}"
        )

    def _on_submit(self):
        self.log.append("Form submitted.")
        payload = {
            "date":          self.date_edit.date().toString("yyyy-MM-dd"),
            "postal_code":   self.postal.text().strip(),
            "prefecture":    self.prefecture.text(),
            "city":          self.city.text(),
            "town":          self.town.text(),
            "prefecture_en": self.prefecture_en.text(),
            "city_en":       self.city_en.text(),
            "town_en":       self.town_en.text(),
            "address2":      self.address2.text().strip(),
        }
        self.submit_btn.setEnabled(False)
        self.data_submitted.emit(payload)
