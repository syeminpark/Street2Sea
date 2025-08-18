# interface.py

import json
from PyQt5.QtCore import QUrl, pyqtSignal, Qt, QSize, QEvent
from PyQt5.QtGui import QPixmap, QKeySequence
from PyQt5.QtWidgets import (
    QWidget, QSizePolicy, QToolButton, QStyle, QShortcut, QApplication, QVBoxLayout
)
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest

from interface_ui import AddressFormUI
from constants import PerspectiveMode
from cesiumViewer import CesiumViewer
from imageViewer import ImageViewerDialog
from connector_overlay import ConnectorOverlay

from pathlib import Path

class ClickCatcher(QWidget):
    hovered = pyqtSignal(bool)
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

    def paintEvent(self, _):  # invisible
        pass

    def enterEvent(self, _):
        self.hovered.emit(True)

    def leaveEvent(self, _):
        self.hovered.emit(False)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(ev)


class AddressForm(AddressFormUI):
    data_submitted = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        # Track both content-sized pixmap fit and the label's OUTER size (for the map)
        self._streetview_outer_size = QSize(self.boxWidth, self.boxHeight)

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

        # connector overlay (top-level window above QWebEngineView)
        self.connector = ConnectorOverlay(self)
        self.connector.set_widgets(self.img1_label, self.cesium_media_frame, self.img2_label)

        self.prefecture.textChanged.connect(self.update_submit_state)
        self.city.textChanged.connect(self.update_submit_state)
        self.town.textChanged.connect(self.update_submit_state)

        self.current_uuid = None  # track which image/uuid is active

        self.cesium_media_frame.installEventFilter(self)
        self.cesium_media_frame.setCursor(Qt.PointingHandCursor)
        self.cesium_media_frame.setAttribute(Qt.WA_Hover, True)
        self.cesium_media_frame.setMouseTracking(True)

        self.cesium_placeholder.installEventFilter(self)
        self.cesium_placeholder.setCursor(Qt.PointingHandCursor)
        self.cesium_placeholder.setAttribute(Qt.WA_Hover, True)
        self.cesium_placeholder.setMouseTracking(True)

        self.cesium_viewer.setCursor(Qt.PointingHandCursor)
        self.cesium_viewer.hoverChanged.connect(self._set_cesium_hover)
        self.cesium_viewer.leftClicked.connect(self._open_mask_for_current_uuid)
        self.cesium_viewer.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    # ---------- enable submit when minimal fields present ----------
    def update_submit_state(self):
        has_postal = bool(self.postal.text().strip())
        has_addr2 = bool(self.address2.text().strip())
        has_core   = all(f.text().strip() for f in (self.prefecture, self.city, self.town))
        self.submit_btn.setEnabled(has_postal and has_addr2 and has_core)

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
        self.log.clear()   
        mode = (
            PerspectiveMode.SURROUNDING if self.rb_surrounding.isChecked()
            else PerspectiveMode.BUILDING
        )
        self.log.append("Input Form submitted.")
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
        self.connector.reset()

    # ---------- Cesium embedding ----------
    def ensure_map_started(self):
        if getattr(self, "_map_initialized", False):
            return

        container = getattr(self, "cesium_media_frame", None)
        if container is None:
            container = getattr(self.cesium_panel, "body", self.cesium_panel)

        layout = container.layout()
        if layout is None:
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

        if self.cesium_placeholder.parent() is not container:
            self.cesium_placeholder.setParent(container)

        layout.replaceWidget(self.cesium_placeholder, self.cesium_viewer)
        self.cesium_placeholder.hide()
        self.cesium_viewer.show()

        self.cesium_viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Invisible layer ABOVE the viewer
        self._cesium_click_layer = ClickCatcher(container)
        self._cesium_click_layer.setGeometry(container.rect())
        self._cesium_click_layer.hovered.connect(self._set_cesium_hover)
        self._cesium_click_layer.clicked.connect(self._open_mask_for_current_uuid)
        self._cesium_click_layer.raise_()

        self._map_initialized = True

        self.connector.set_widgets(self.img1_label, self.cesium_media_frame, self.img2_label)
        self.connector.update()

        # Size the Cesium frame to MATCH the Street-View label's OUTER size
        self._update_cesium_frame_size()

        layout.invalidate()
        layout.activate()
        QApplication.processEvents()

    def _update_cesium_frame_size(self):
        """Make the middle (Cesium) card exactly the same outer size as the Street-View label."""
        if not hasattr(self, "cesium_media_frame"):
            return
        outer = getattr(self, "_streetview_outer_size", self.img1_label.size())
        if outer.width() > 0 and outer.height() > 0:
            self.cesium_media_frame.setFixedSize(outer)
            if hasattr(self, "_cesium_click_layer") and self._cesium_click_layer:
                self._cesium_click_layer.setGeometry(self.cesium_media_frame.rect())

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

        # keep Cesium the same visible size as Street-View
        if getattr(self, "_map_initialized", False):
            self._update_cesium_frame_size()

    def _show_current_street(self):
        img_bytes = self.street_images[self.current_street_index]
        pix = QPixmap()
        if pix.loadFromData(img_bytes):
            self._current_street_pix = pix
            target = self.img1_label.contentsRect().size()
            if target.width() > 0 and target.height() > 0:
                scaled = pix.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.img1_label.setPixmap(scaled)

            # OUTER size drives Cesium frame size
            self._streetview_outer_size = self.img1_label.size()
            if getattr(self, "_map_initialized", False):
                self._update_cesium_frame_size()

            meta = self.street_meta[self.current_street_index]
            self.current_uuid = meta.get("uuid", getattr(self, "current_uuid", None))
            

            meta_text = ', '.join(f"{k}: {v}" for k, v in meta.items())
            idx = self.current_street_index + 1
            total = len(self.street_images)
            self.log.append(f"\n✔ Street-View {idx}/{total} displayed.")
            # self.log.append(f"\n✔ Street-View {idx}/{total} displayed ({meta_text}).")
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
        s = 36
        w = self.img1_label.width()
        h = self.img1_label.height()
        y = max(0, (h - s) // 2)
        self.prev_btn.move(8, y)
        self.next_btn.move(max(8, w - s - 8), y)

    def eventFilter(self, obj, ev):
        # Re-fit Street-View pixmap and sync Cesium size whenever label resizes/shows
        if obj is self.img1_label and ev.type() in (QEvent.Resize, QEvent.Show):
            if not self._current_street_pix.isNull():
                target = self.img1_label.contentsRect().size()
                if target.width() > 0 and target.height() > 0:
                    self.img1_label.setPixmap(
                        self._current_street_pix.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    )
            # update OUTER size and apply to Cesium
            self._streetview_outer_size = self.img1_label.size()
            if getattr(self, "_map_initialized", False):
                self._update_cesium_frame_size()
            self._position_nav_buttons()

        if obj is self.img2_label and ev.type() in (QEvent.Resize, QEvent.Show):
            if not self._current_ai_pix.isNull():
                target = self.img2_label.contentsRect().size()
                if target.width() > 0 and target.height() > 0:
                    self.img2_label.setPixmap(
                        self._current_ai_pix.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    )

        # keep click layer covering the frame
        if obj is self.cesium_media_frame and ev.type() in (QEvent.Resize, QEvent.Show, QEvent.Move):
            if hasattr(self, "_cesium_click_layer") and self._cesium_click_layer:
                self._cesium_click_layer.setGeometry(self.cesium_media_frame.rect())

        # hover/click handling for frame/placeholder
        if obj in (self.cesium_media_frame, self.cesium_placeholder):
            if ev.type() in (QEvent.Enter, QEvent.HoverEnter, QEvent.HoverMove):
                self._set_cesium_hover(True)
            elif ev.type() in (QEvent.Leave, QEvent.HoverLeave):
                self._set_cesium_hover(False)
            elif ev.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
                if getattr(ev, "button", lambda: None)() == Qt.LeftButton:
                    self._open_mask_for_current_uuid()
                    return True

        return super().eventFilter(obj, ev)

    def _set_cesium_hover(self, on: bool):
        f = self.cesium_media_frame
        if f.property("hover") == on:
            return
        f.setProperty("hover", on)
        f.style().unpolish(f)
        f.style().polish(f)
        f.update()

    # ---------- AI image ----------
    def display_ai_image(self, img_bytes: bytes):
        pix = QPixmap()
        if pix.loadFromData(img_bytes):
            self._current_ai_pix = pix
            target = self.img2_label.contentsRect().size()
            if target.width() > 0 and target.height() > 0:
                scaled = pix.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.img2_label.setPixmap(scaled)
            self.log.append("✔ AI-generated image displayed.\n")
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

    def _open_mask_for_current_uuid(self):
        uuid = getattr(self, "current_uuid", None)
        if not uuid:
            self.log.append("⚠ No Flood Mask to show.")
            return

        base = Path("images")
        candidates = [
            base / f"{uuid}_underwater_mask.png",
            base / f"{uuid}_overwater_mask.png",
        ]

        for p in candidates:
            if p.exists():
                pix = QPixmap(str(p))
                if pix.isNull():
                    self.log.append(f"⚠ Failed to load mask: {p.name}")
                    return
                title = "Mask (underwater)" if "underwater" in p.name else "Mask (overwater)"
                dlg = ImageViewerDialog(title, self)
                dlg.set_pixmap(pix)
                dlg.exec_()
                return

        self.log.append("⚠ Mask not found yet for this view (still generating?).")
