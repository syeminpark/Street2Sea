import json
from PyQt5.QtCore import QUrl, pyqtSignal, Qt,  QSize   
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QPushButton, QHBoxLayout, QLabel, QWidget, QSizePolicy
)
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
from interface_ui import AddressFormUI
from constants import PerspectiveMode
from cesiumViewer import CesiumViewer


class AddressForm(AddressFormUI):
    data_submitted = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._streetview_size = QSize(self.boxWidth, self.boxHeight)

        self._cesium_ready     = False
        self._pending_payloads = []

        # image navigation state
        self.street_images = []
        self.street_meta = []
        self.current_street_index = 0

        # connect form signals
        self.postal.editingFinished.connect(self.lookup_postal)
        self.postal.textChanged.connect(self.update_submit_state)
        self.address2.textChanged.connect(self.update_submit_state)
        self.submit_btn.clicked.connect(self._on_submit)
        self.tz_combo.currentIndexChanged.connect(self.update_submit_state)

        # create navigation widget sized to the street-view label
        self.nav_widget = QWidget()
        self.nav_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        nav_layout = QHBoxLayout(self.nav_widget)
        nav_layout.setContentsMargins(0,0,0,0)
        nav_layout.setSpacing(5)

        self.prev_btn = QPushButton("Prev")
        self.next_btn = QPushButton("Next")
        for b in (self.prev_btn, self.next_btn):
            b.setEnabled(False)

        nav_layout.addWidget(self.prev_btn, 1)
        nav_layout.addWidget(self.next_btn, 1)

        parent = self.img1_label.parentWidget().layout()
        parent.insertWidget(2, self.nav_widget, alignment=Qt.AlignHCenter)

        # postal lookup
        self.net = QNetworkAccessManager(self)
        self.net.finished.connect(self._on_api_response)

        # prepare Cesium
        self.cesium_viewer = CesiumViewer()
        self.cesium_viewer.loadFinished.connect(self._on_cesium_ready)  # <<<

        self.update_submit_state()

    def update_submit_state(self):
        has_postal = bool(self.postal.text().strip())
        has_addr2 = bool(self.address2.text().strip())
        self.submit_btn.setEnabled(has_postal and has_addr2)

    def lookup_postal(self):
        code = self.postal.text().strip().replace('-', '')
        if len(code) != 7 or not code.isdigit():
            return
        self.log.append(f"Looking up postal code {code}…")
        url = QUrl(f"https://zipcloud.ibsnet.co.jp/api/search?zipcode={code}")
        self.net.get(QNetworkRequest(url))

    def _on_api_response(self, reply):
        if reply.error():
            self.log.append(f"Lookup failed: {reply.errorString()}")
            return
        data = json.loads(bytes(reply.readAll()).decode())
        if data.get('status') != 200 or not data.get('results'):
            self.log.append("No address found for that postal code.")
            return
        r = data['results'][0]
        self.prefecture.setText(r['address1'])
        self.city.setText(r['address2'])
        self.town.setText(r['address3'])
        self.prefecture_en.setText(self.converter.do(r['address1']))
        self.city_en.setText(self.converter.do(r['address2']))
        self.town_en.setText(self.converter.do(r['address3']))
        self.log.append(
            f"Address found: {r['address1']} {r['address2']} {r['address3']}"
        )

    def _on_submit(self):
        mode = (
            PerspectiveMode.SURROUNDING if self.rb_surrounding.isChecked()
            else PerspectiveMode.BUILDING
        )
        self.log.append("Form submitted.")
        payload = {
            'date': self.date_edit.date().toString('yyyy-MM-dd'),
            'time': self.time_edit.time().toString('HH:mm'),
            'postal_code': self.postal.text().strip(),
            'prefecture': self.prefecture.text(),
            'city': self.city.text(),
            'town': self.town.text(),
            'prefecture_en': self.prefecture_en.text(),
            'city_en': self.city_en.text(),
            'town_en': self.town_en.text(),
            'address2': self.address2.text().strip(),
            'mode': mode.value,
            'timezone': self.tz_combo.currentText(),
        }
        self.submit_btn.setEnabled(False)
        self.data_submitted.emit(payload)


    def ensure_map_started(self):
        if getattr(self, "_map_initialized", False):
            return

        layout = self.cesium_panel.layout()
        layout.replaceWidget(self.cesium_placeholder, self.cesium_viewer)

        # use the *content* size, not the label’s box
        w = self._streetview_size.width()
        h = self._streetview_size.height()

        self.cesium_viewer.setFixedSize(w, h)
        self.cesium_viewer.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.cesium_placeholder.deleteLater()
        self._map_initialized = True
    
    def set_street_images(self, images, metadata):
        self.street_images = images
        self.street_meta   = metadata
        self.current_street_index = 0

        # parse the size string into two ints
        size_str = metadata[0].get("size", "600x300")
        w, h = map(int, size_str.split("x"))

        # resize your Street-View QLabel
        # self.img1_label.setFixedSize(w, h)

        

        # now show the first image
        self._show_current_street()
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(len(images) > 1)

        # finally, if Cesium is already in the UI, clamp it now
        if getattr(self, "_map_initialized", False):
            s = self._streetview_size
            self.cesium_viewer.setFixedSize(s)
            # self.cesium_viewer.viewer.resize()


    def _show_current_street(self):
        img_bytes = self.street_images[self.current_street_index]
        pix = QPixmap()
        if pix.loadFromData(img_bytes):
            scaled = pix.scaled(
                self.img1_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.img1_label.setPixmap(scaled)
            self.img1_label.setFixedSize(scaled.size()) 

            # NEW: remember the real on-screen size
            self._streetview_size = scaled.size()

            meta = self.street_meta[self.current_street_index]
            meta_text = ', '.join(f"{k}: {v}" for k, v in meta.items())
            idx = self.current_street_index + 1
            total = len(self.street_images)
            self.log.append(
                f"✔ Street‑View {idx}/{total} displayed ({meta_text})."
            )
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
