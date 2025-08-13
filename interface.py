# interface.py

import json
from PyQt5.QtCore import QUrl, pyqtSignal, Qt, QSize, QEvent
from PyQt5.QtGui import QPixmap, QKeySequence
from PyQt5.QtWidgets import (
    QWidget, QSizePolicy, QToolButton, QStyle, QShortcut
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
        self.date_edit.dateChanged.connect(self.update_submit_state)
        self.time_edit.timeChanged.connect(self.update_submit_state)
        self.rb_building.toggled.connect(self.update_submit_state)
        self.rb_surrounding.toggled.connect(self.update_submit_state)
        self.depth_override_cb.toggled.connect(self.update_submit_state)
        self.depth_override_spin.valueChanged.connect(self.update_submit_state)

        # --- floating nav buttons inside the Street-View image ---
        self.prev_btn = QToolButton(self.img1_label)
        self.next_btn = QToolButton(self.img1_label)
        for b in (self.prev_btn, self.next_btn):
            b.setAutoRaise(True)
            b.setFixedSize(36, 36)
            b.setStyleSheet("""
                QToolButton {
                    border: none;
                    border-radius: 18px;
                    background: rgba(0,0,0,0.35);
                    color: white;
                }
                QToolButton:hover { background: rgba(0,0,0,0.55); }
                QToolButton:disabled { background: rgba(0,0,0,0.2); color: rgba(255,255,255,0.5); }
            """)
        self.prev_btn.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))
        self.next_btn.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
        self.prev_btn.setToolTip("Previous Street-View")
        self.next_btn.setToolTip("Next Street-View")
        self.prev_btn.clicked.connect(self.show_prev_street_image)
        self.next_btn.clicked.connect(self.show_next_street_image)
        self.prev_btn.hide()
        self.next_btn.hide()
        # keep chevrons centered when label resizes
        self.img1_label.installEventFilter(self)
        # keyboard shortcuts
        QShortcut(QKeySequence(Qt.Key_Left),  self, activated=self.show_prev_street_image)
        QShortcut(QKeySequence(Qt.Key_Right), self, activated=self.show_next_street_image)

        # postal lookup
        self.net = QNetworkAccessManager(self)
        self.net.finished.connect(self._on_api_response)

        # prepare Cesium
        self.cesium_viewer = CesiumViewer()

        self.update_submit_state()

        self._current_street_pix = QPixmap()
        self._current_ai_pix = QPixmap()
        self.img1_label.clicked.connect(lambda: self._open_viewer(self._current_street_pix, "Street-View"))
        self.img2_label.clicked.connect(lambda: self._open_viewer(self._current_ai_pix, "AI-Generated"))

        # connector overlay (top-level window that sits above QWebEngineView)
        self.connector = ConnectorOverlay(self)
        # initially connect to the placeholder in the middle
        self.connector.set_widgets(self.img1_label, self.cesium_placeholder, self.img2_label)

    # ---------- enable submit when minimal fields present ----------
    def update_submit_state(self):
        has_postal = bool(self.postal.text().strip())
        has_addr2 = bool(self.address2.text().strip())
        self.submit_btn.setEnabled(has_postal and has_addr2)

    # ---------- postal lookup ----------
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
        self.log.append(f"Address found: {r['address1']} {r['address2']} {r['address3']}")
        self.update_submit_state()

    # ---------- submit ----------
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
            'depth_override_enabled': self.depth_override_cb.isChecked(),
            'depth_override_value': float(self.depth_override_spin.value()),
        }
        self.submit_btn.setEnabled(False)
        self.data_submitted.emit(payload)
        # reset connector states each run
        self.connector.reset()

    # ---------- Cesium embedding ----------
    def ensure_map_started(self):
        if getattr(self, "_map_initialized", False):
            return

        layout = self.cesium_panel.layout()
        layout.replaceWidget(self.cesium_placeholder, self.cesium_viewer)

        # content size (match the Street-View label)
        w = self._streetview_size.width()
        h = self._streetview_size.height()
        self.cesium_viewer.setFixedSize(w, h)
        self.cesium_viewer.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.cesium_placeholder.deleteLater()
        self._map_initialized = True

        self.connector.set_widgets(self.img1_label, self.cesium_viewer, self.img2_label)
        self.connector.update()

    # ---------- images ----------
    def set_street_images(self, images, metadata):
        self.street_images = images
        self.street_meta   = metadata
        self.current_street_index = 0
        self.img2_label.clear()

        # show the first image
        self._show_current_street()

        count = len(images)
        self.prev_btn.setVisible(count > 1)
        self.next_btn.setVisible(count > 1)
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(count > 1)
        self._position_nav_buttons()

        # update cesium size if already placed
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
            # remember the real on-screen size
            self._streetview_size = scaled.size()

            meta = self.street_meta[self.current_street_index]
            meta_text = ', '.join(f"{k}: {v}" for k, v in meta.items())
            idx = self.current_street_index + 1
            total = len(self.street_images)
            self.log.append(f"✔ Street-View {idx}/{total} displayed ({meta_text}).")
        else:
            self.log.append("⚠ Failed to load Street-View image data.")
        self._position_nav_buttons()

    def show_prev_street_image(self):
        if self.current_street_index > 0:
            self.current_street_index -= 1
            self._show_current_street()
        self.prev_btn.setEnabled(self.current_street_index > 0)
        self.next_btn.setEnabled(self.current_street_index < len(self.street_images) - 1)
        self._position_nav_buttons()

    def show_next_street_image(self):
        if self.current_street_index < len(self.street_images) - 1:
            self.current_street_index += 1
            self._show_current_street()
        self.prev_btn.setEnabled(self.current_street_index > 0)
        self.next_btn.setEnabled(self.current_street_index < len(self.street_images) - 1)
        self._position_nav_buttons()

    def _position_nav_buttons(self):
        # center vertically; 8px margin from the left/right edge
        s = 36
        w = self.img1_label.width()
        h = self.img1_label.height()
        y = max(0, (h - s) // 2)
        self.prev_btn.move(8, y)
        self.next_btn.move(max(8, w - s - 8), y)

    def eventFilter(self, obj, ev):
        if obj is self.img1_label and ev.type() in (QEvent.Resize, QEvent.Show):
            self._position_nav_buttons()
        return super().eventFilter(obj, ev)

    # ---------- AI image ----------
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
            self.connector.set_ai_ready(True)
        else:
            self.log.append("⚠ Failed to load AI-generated image.")

    # ---------- viewer popup ----------
    def _open_viewer(self, pix: QPixmap, title: str):
        if pix.isNull():
            self.log.append(f"⚠ No {title} image to show.")
            return
        dlg = ImageViewerDialog(title, self)
        dlg.set_pixmap(pix)
        dlg.exec_()

    # ---------- connector hooks ----------
    def on_tiles_ready(self):
        self.connector.set_tiles_ready(True)
