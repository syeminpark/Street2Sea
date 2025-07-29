import json
from PyQt5.QtCore import QUrl, pyqtSignal, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QPushButton, QHBoxLayout, QLabel
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
from interface_ui import AddressFormUI
from constants import PerspectiveMode


class AddressForm(AddressFormUI):
    data_submitted = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

        # image navigation state
        self.street_images = []           # list of raw bytes
        self.street_meta   = []           # list of metadata dicts
        self.current_street_index = 0

        # connect signals
        self.postal.editingFinished.connect(self.lookup_postal)
        self.postal.textChanged.connect(self.update_submit_state)
        self.address2.textChanged.connect(self.update_submit_state)
        self.submit_btn.clicked.connect(self._on_submit)
        self.tz_combo.currentIndexChanged.connect(self.update_submit_state)

        # add Prev/Next buttons under Street‑View panel
        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("Prev")
        self.next_btn = QPushButton("Next")
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.prev_btn.clicked.connect(self.show_prev_street_image)
        self.next_btn.clicked.connect(self.show_next_street_image)
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.next_btn)
        parent_layout = self.img1_label.parentWidget().layout()
        parent_layout.insertLayout(2, nav_layout)


        # postal lookup manager
        self.net = QNetworkAccessManager(self)
        self.net.finished.connect(self._on_api_response)

        # initialize button state
        self.update_submit_state()

    def update_submit_state(self):
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
        mode = (
        PerspectiveMode.SURROUNDING
        if self.rb_surrounding.isChecked()
        else PerspectiveMode.BUILDING
        )

        self.log.append("Form submitted.")
        payload = {
            "date":          self.date_edit.date().toString("yyyy-MM-dd"),
            "time":  self.time_edit.time().toString("HH:mm"),
            "postal_code":   self.postal.text().strip(),
            "prefecture":    self.prefecture.text(),
            "city":          self.city.text(),
            "town":          self.town.text(),
            "prefecture_en": self.prefecture_en.text(),
            "city_en":       self.city_en.text(),
            "town_en":       self.town_en.text(),
            "address2":      self.address2.text().strip(),
            "mode":mode.value,
            "timezone":      self.tz_combo.currentText(),   
        }
        self.submit_btn.setEnabled(False)
        self.data_submitted.emit(payload)

    def set_street_images(self, images, metadata):
        """
        Accepts:
          images: list of raw bytes
          metadata: list of dicts (e.g. {'heading':0}, ...)
        """
        self.street_images = images
        self.street_meta   = metadata
        self.current_street_index = 0
        self._show_current_street()
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(len(images) > 1)

    def _show_current_street(self):
        img_bytes = self.street_images[self.current_street_index]
        pix = QPixmap()
        if pix.loadFromData(img_bytes):
            self.img1_label.setPixmap(pix)
            # show metadata
            meta = self.street_meta[self.current_street_index]
            meta_text = ", ".join(f"{k}: {v}" for k, v in meta.items())
            idx = self.current_street_index + 1
            total = len(self.street_images)
            self.log.append(f"✔ Street‑View {idx}/{total} displayed ({meta_text}).")
        else:
            self.log.append("⚠ Failed to load Street‑View image data.")

    def show_prev_street_image(self):
        if self.current_street_index > 0:
            self.current_street_index -= 1
            self._show_current_street()
        self.prev_btn.setEnabled(self.current_street_index > 0)
        self.next_btn.setEnabled(self.current_street_index < len(self.street_images) - 1)

    def show_next_street_image(self):
        if self.current_street_index < len(self.street_images) - 1:
            self.current_street_index += 1
            self._show_current_street()
        self.prev_btn.setEnabled(self.current_street_index > 0)
        self.next_btn.setEnabled(self.current_street_index < len(self.street_images) - 1)

    def display_ai_image(self, img_bytes: bytes):
        pix = QPixmap()
        if pix.loadFromData(img_bytes):
            self.img2_label.setPixmap(pix)
            self.log.append("✔ AI‑generated image displayed.")
        else:
            self.log.append("⚠ Failed to load AI‑generated image.")