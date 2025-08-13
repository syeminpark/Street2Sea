# interface.py

import json
from PyQt5.QtCore import QUrl, pyqtSignal, Qt, QSize, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QPushButton, QHBoxLayout, QLabel, QWidget, QSizePolicy
)
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest

from interface_ui import AddressFormUI
from constants import PerspectiveMode
from cesiumViewer import CesiumViewer
from imageViewer import ImageViewerDialog
from connector_overlay import ConnectorOverlay


class AddressForm(AddressFormUI):
    data_submitted = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._streetview_size = QSize(self.boxWidth, self.boxHeight)

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

        # more signals that should re-enable submit
        self.date_edit.dateChanged.connect(self.update_submit_state)
        self.time_edit.timeChanged.connect(self.update_submit_state)
        self.rb_building.toggled.connect(self.update_submit_state)
        self.rb_surrounding.toggled.connect(self.update_submit_state)
        self.depth_override_cb.toggled.connect(self.update_submit_state)
        self.depth_override_spin.valueChanged.connect(self.update_submit_state)

        # create navigation widget sized to the street-view label
        self.nav_widget = QWidget()
        self.nav_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        nav_layout = QHBoxLayout(self.nav_widget)
        nav_layout.setContentsMargins(0, 0, 0, 0)
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

        # prepare Cesium (QWebEngineView wrapper)
        self.cesium_viewer = CesiumViewer()

        # image zoom viewers
        self._current_street_pix = QPixmap()
        self._current_ai_pix = QPixmap()
        self.img1_label.clicked.connect(
            lambda: self._open_viewer(self._current_street_pix, "Street-View")
        )
        self.img2_label.clicked.connect(
            lambda: self._open_viewer(self._current_ai_pix, "AI-Generated")
        )

        self.update_submit_state()
        self.prev_btn.clicked.connect(self.show_prev_street_image)
        self.next_btn.clicked.connect(self.show_next_street_image)

        # create the connector overlay AFTER first layout pass
        self._connector = None


    # -------- overlay init --------
    def _init_connector(self):
        if self._connector:
            return
        # Top-level, always-on-top overlay that draws above QWebEngineView
        self._connector = ConnectorOverlay(self)
        # initially connect to the placeholder in the middle
        self._connector.set_widgets(self.img1_label, self.cesium_placeholder, self.img2_label)
        # set these to False if you prefer hidden lines while waiting
        self._connector.animate_when_waiting_line1 = True   # street -> 3D
        self._connector.animate_when_waiting_line2 = True   # 3D -> AI

    # -------- form plumbing --------
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
        self.update_submit_state()

    def _on_submit(self):
        mode = (
            PerspectiveMode.SURROUNDING if self.rb_surrounding.isChecked()
            else PerspectiveMode.BUILDING
        )
        self.log.append("Form submitted.")
        self._init_connector()

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
            'depth_override_enabled': self.depth_override_cb.isChecked(),
            'depth_override_value': float(self.depth_override_spin.value()),
        }
        # disable until something changes again
        self.submit_btn.setEnabled(False)
        # new run => lines go back to waiting
        if self._connector:
            self._connector.reset()
        self.data_submitted.emit(payload)

    # -------- cesium panel --------
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

        # point overlay at the real viewer now
        if self._connector:
            self._connector.set_widgets(self.img1_label, self.cesium_viewer, self.img2_label)
            self._connector.update()

    # -------- street images --------
    def set_street_images(self, images, metadata):
        self.street_images = images
        self.street_meta   = metadata
        self.current_street_index = 0
        self.img2_label.clear()

        # parse the size string into two ints (e.g. "640x640")
        size_str = metadata[0].get("size", "600x300")
        try:
            w, h = map(int, size_str.split("x"))
        except Exception:
            w, h = self.boxWidth, self.boxHeight

        # show the first image
        self._show_current_street()
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(len(images) > 1)

        # clamp Cesium if already initialized
        if getattr(self, "_map_initialized", False):
            s = self._streetview_size
            self.cesium_viewer.setFixedSize(s)

    def _show_current_street(self):
        img_bytes = self.street_images[self.current_street_index]
        pix = QPixmap()
        if pix.loadFromData(img_bytes):
            self._current_street_pix = pix
            scaled = pix.scaled(
                self.img1_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.img1_label.setPixmap(scaled)
            self.img1_label.setFixedSize(scaled.size())

            # remember real on-screen size for Cesium panel
            self._streetview_size = scaled.size()

            meta = self.street_meta[self.current_street_index]
            meta_text = ', '.join(f"{k}: {v}" for k, v in meta.items())
            idx = self.current_street_index + 1
            total = len(self.street_images)
            self.log.append(f"✔ Street-View {idx}/{total} displayed ({meta_text}).")
        else:
            self.log.append("⚠ Failed to load Street-View image data.")

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

    # -------- AI image --------
    def display_ai_image(self, img_bytes: bytes):
        pix = QPixmap()
        if pix.loadFromData(img_bytes):
            self._current_ai_pix = pix
            scaled = pix.scaled(
                self.img2_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.img2_label.setPixmap(scaled)
            self.log.append("✔ AI-generated image displayed.")
            if self._connector:
                self._connector.set_ai_ready(True)
        else:
            self.log.append("⚠ Failed to load AI-generated image.")

    # -------- connectors state from app.py --------
    def on_tiles_ready(self):
        if self._connector:
            self._connector.set_tiles_ready(True)

    # -------- zoom dialog --------
    def _open_viewer(self, pix: QPixmap, title: str):
        if pix.isNull():
            self.log.append(f"⚠ No {title} image to show.")
            return
        dlg = ImageViewerDialog(title, self)
        dlg.set_pixmap(pix)
        dlg.exec_()

    # keep overlay aligned if user moves/resizes/closes this window
    def moveEvent(self, e):
        if self._connector:
            self._connector._reposition()
        super().moveEvent(e)

    def resizeEvent(self, e):
        if self._connector:
            self._connector._reposition()
        super().resizeEvent(e)

    def closeEvent(self, e):
        if self._connector:
            self._connector.close()
        super().closeEvent(e)
