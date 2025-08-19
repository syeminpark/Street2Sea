# interface_ui.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QDateEdit, QLineEdit, QPushButton, QTextEdit, QLabel,
    QSizePolicy, QRadioButton, QButtonGroup, QTimeEdit, QComboBox,
    QApplication, QDesktopWidget, QCheckBox, QDoubleSpinBox, QFrame,
    QGraphicsDropShadowEffect, QAbstractSpinBox, QStyleFactory, QProxyStyle
)
from PyQt5.QtCore import QDate, QTime, Qt, QEvent, QRect, QRectF, QPoint, QLineF
from PyQt5.QtGui import QColor, QPainter, QPalette, QPolygon, QPainterPath, QPen
from pykakasi import kakasi

from interface_utility import make_autofill_on_tab
from clickable_label import ClickableLabel
from constants import FONTS, FONT_STACKS, to_css_stack, PALETTE
from title import VerticalTitle


# ---------- visual helpers ----------


class DropShadowCard(QWidget):
    def __init__(self, blur=24, y=10, alpha=140, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setContentsMargins(0, 0, 0, 0)

        self._backer = QWidget(self)
        self._backer.setAttribute(Qt.WA_StyledBackground, True)
        self._backer.setAutoFillBackground(True)
        self._backer.setStyleSheet(
            f"background-color: {PALETTE.surface};"
            f"border: 1px solid {PALETTE.border};"
            f"border-radius: 12px;"
        )
        eff = QGraphicsDropShadowEffect(self._backer)
        eff.setBlurRadius(blur); eff.setXOffset(0); eff.setYOffset(y)
        eff.setColor(QColor(0, 0, 0, alpha))
        self._backer.setGraphicsEffect(eff)

        self.body = QWidget(self)
        self.body.setAttribute(Qt.WA_StyledBackground, True)
        self.body.setAutoFillBackground(True)
        self.body.setStyleSheet(
            f"background-color: {PALETTE.surface};"
            f"border: 1px solid {PALETTE.border};"
            f"border-radius: 12px;"
        )

        self._backer.lower()
        self.body.raise_()

    def resizeEvent(self, ev):
        r = self.rect()
        self._backer.setGeometry(r)
        self.body.setGeometry(r)
        super().resizeEvent(ev)


class TitlePillOverlay(QWidget):
    def __init__(self, parent: QWidget, title_label: QLabel, radius=10):
        super().__init__(parent)
        self._title = title_label
        self._radius = radius
        self.setProperty("role", "overlay")
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        parent.installEventFilter(self)
        title_label.installEventFilter(self)

        self.setGeometry(parent.rect())
        self.raise_(); self.show()

    def _pill_rect(self) -> QRect:
        lbl = self._title
        content = lbl.contentsRect()
        fm = lbl.fontMetrics()
        text = lbl.text()
        text_w = min(fm.horizontalAdvance(text), content.width())
        text_h = fm.boundingRect(text).height()
        x = content.x() + (content.width()  - text_w) / 2.0
        y = content.y() + (content.height() - text_h) / 2.0
        tl = lbl.mapTo(self.parent(), QPoint(int(x), int(y)))
        pad_x, pad_y = 10, 6
        return QRect(tl.x() - pad_x, tl.y() - pad_y,
                     int(text_w + 2 * pad_x), int(text_h + 2 * pad_y))

    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.Resize, QEvent.Move, QEvent.Show,
                         QEvent.FontChange, QEvent.StyleChange, QEvent.LayoutRequest):
            if obj is self.parent():
                self.setGeometry(self.parent().rect())
            self.update()
        return False

    def paintEvent(self, _):
        if not self._title.isVisible():
            return
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 130))
            r = QRectF(self._pill_rect()); r.adjust(-0.5, -0.5, +0.5, +0.5)
            p.drawRoundedRect(r, self._radius, self._radius)
        finally:
            p.end()


class BrightSpinArrowsStyle(QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget=None):
        from PyQt5.QtWidgets import QStyle
        if element in (QStyle.PE_IndicatorSpinUp, QStyle.PE_IndicatorSpinDown):
            r = option.rect; rr = r.adjusted(0, 0, -1, -1)
            painter.save(); painter.setRenderHint(QPainter.Antialiasing, True)
            pen = QPen(QColor(PALETTE.border)); pen.setCosmetic(True); pen.setWidthF(1.0)
            painter.setPen(pen); x = rr.left() + 0.5
            painter.drawLine(QLineF(x, rr.top(), x, rr.bottom()))
            arrow = QColor(PALETTE.text) if (option.state & QStyle.State_Enabled) else QColor(255, 255, 255, 120)
            m = max(2, min(5, int(min(rr.width(), rr.height()) * 0.14)))
            ar = rr.adjusted(m, m, -m, -m)
            if element == QStyle.PE_IndicatorSpinUp:
                tri = QPolygon([QPoint(ar.center().x(), ar.top()), QPoint(ar.right(), ar.bottom()), QPoint(ar.left(), ar.bottom())])
            else:
                tri = QPolygon([QPoint(ar.left(), ar.top()), QPoint(ar.right(), ar.top()), QPoint(ar.center().x(), ar.bottom())])
            painter.setPen(Qt.NoPen); painter.setBrush(arrow); painter.drawPolygon(tri)
            painter.restore(); return
        return super().drawPrimitive(element, option, painter, widget)


# ---------- main UI ----------

class AddressFormUI(QWidget):
    def __init__(self):
        self.boxWidth = 512
        self.boxHeight = 512
        super().__init__()

        QApplication.setStyle(QStyleFactory.create("Fusion"))
        QApplication.setStyle(BrightSpinArrowsStyle(QApplication.style()))

        self._build_ui()
        make_autofill_on_tab(self.postal)
        make_autofill_on_tab(self.address2)
        self._apply_styles()
        self._postprocess_spinboxes()
        self._init_kakasi()
        self._install_vertical_title()

    # helpers
    def _add_shadow(self, w, blur=24, y=10, alpha=140):
        eff = QGraphicsDropShadowEffect(self)
        eff.setBlurRadius(blur); eff.setXOffset(0); eff.setYOffset(y)
        eff.setColor(QColor(0, 0, 0, alpha))
        w.setGraphicsEffect(eff)

    def _make_hline(self) -> QWidget:
        spacer = QWidget()
        spacer.setFixedHeight(6)
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        spacer.setAttribute(Qt.WA_StyledBackground, False)
        return spacer

    def _make_image_panel(self, title_text, attr_name, desc):
        panel = QWidget(); panel.setProperty("panel", "card")
        pv = QVBoxLayout(panel); pv.setContentsMargins(10, 8, 10, 10); pv.setSpacing(5)

        title = self._make_title(title_text)
        pv.addWidget(title, alignment=Qt.AlignCenter)
        TitlePillOverlay(panel, title)

        lbl = ClickableLabel(alignment=Qt.AlignCenter)
        lbl.setCursor(Qt.PointingHandCursor)
        lbl.setMinimumSize(self.boxWidth, self.boxHeight)
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lbl.setScaledContents(False)           # no stretch/crop
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setProperty("role", "media")
        lbl.setMargin(0)                       # let stylesheet padding handle inset

        setattr(self, attr_name, lbl)
        pv.addWidget(lbl, alignment=Qt.AlignCenter)
        pv.addWidget(self._make_subtitle(desc), alignment=Qt.AlignCenter)

        self._add_shadow(panel, blur=20, y=8, alpha=120)
        return panel

    def _make_gpu_panel(self, title_text, frame_attr_name, placeholder_attr_name, desc):
        wrapper = DropShadowCard(blur=20, y=8, alpha=120)
        v = QVBoxLayout(wrapper.body); v.setContentsMargins(10, 8, 10, 10); v.setSpacing(5)

        title = self._make_title(title_text)
        v.addWidget(title, alignment=Qt.AlignCenter)
        TitlePillOverlay(wrapper.body, title)

        frame = QFrame()
        frame.setProperty("role", "media")
        frame.setMinimumSize(self.boxWidth, self.boxHeight)
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        frame.setAttribute(Qt.WA_StyledBackground, True)
        frame.setAutoFillBackground(True)
        frame.setObjectName("cesiumFrame")
        frame.setStyleSheet(f"""
            QFrame#cesiumFrame {{
                background-color: {PALETTE.bg};
                border: 2px dashed {PALETTE.border};
                border-radius: 12px;
                padding: 10px;          /* ↑ was 4px */
            }}
            QFrame#cesiumFrame[hover="true"] {{
                border: 2px solid {PALETTE.accent};
            }}
        """)

        fl = QVBoxLayout(frame); fl.setContentsMargins(0,0,0,0); fl.setSpacing(0)

        ph = QLabel("", alignment=Qt.AlignCenter)
        ph.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        ph.setMinimumSize(1, 1)
        ph.setStyleSheet("background-color: transparent; border: none;")
        fl.addWidget(ph, 1)

        setattr(self, frame_attr_name, frame)
        setattr(self, placeholder_attr_name, ph)

        v.addWidget(frame, 0, Qt.AlignCenter)
        v.addWidget(self._make_subtitle(desc), alignment=Qt.AlignCenter)
        return wrapper

    def _build_ui(self):
        screen = QDesktopWidget().availableGeometry(self)
        w = int(screen.width() * 0.7); h = int(screen.height() * 0.95)
        self.setMinimumSize(w, h); self.resize(w, h)
        self.setWindowTitle("SAFE: Street-view AI Images from Forecast Simulations")

        root = QVBoxLayout(self)

        top = QHBoxLayout()

        form_panel = QWidget(); form_panel.setProperty("panel", "card")
        fv = QVBoxLayout(form_panel); fv.setContentsMargins(16, 16, 16, 16); fv.setSpacing(10)

        form_title = self._make_title("Input Form")
        fv.addWidget(form_title); TitlePillOverlay(form_panel, form_title)
        fv.addWidget(self._make_hline())

        rows = QFormLayout()
        rows.setHorizontalSpacing(20); rows.setVerticalSpacing(16)
        rows.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        rows.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        dt_layout = QHBoxLayout()
        self.date_edit = QDateEdit(calendarPopup=True)
        self.date_edit.setDate(QDate(2025, 7, 10))
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        dt_layout.addWidget(self.date_edit)

        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH")
        self.time_edit.setTime(QTime(19, 0))
        self.time_edit.setMinimumTime(QTime(0, 0))
        self.time_edit.setMaximumTime(QTime(23, 0))
        dt_layout.addWidget(self.time_edit)

        self.tz_combo = QComboBox()
        self.tz_combo.addItems(["JST", "UTC"])
        dt_layout.addWidget(self.tz_combo)
        rows.addRow("Date & Time(Hour):", dt_layout)

        self.postal = QLineEdit(); self.postal.setPlaceholderText("e.g. 153-0061")
        rows.addRow("Postal Code:", self.postal)

        self.prefecture = QLineEdit(); self.prefecture.setReadOnly(True)
        self.city = QLineEdit(); self.city.setReadOnly(True)
        self.town = QLineEdit(); self.town.setReadOnly(True)
        rows.addRow("Prefecture:", self.prefecture)
        rows.addRow("City/Ward:", self.city)
        rows.addRow("Town/Suburb:", self.town)

        self.prefecture_en = QLineEdit(); self.prefecture_en.setReadOnly(True)
        self.city_en = QLineEdit(); self.city_en.setReadOnly(True)
        self.town_en = QLineEdit(); self.town_en.setReadOnly(True)
        rows.addRow("Prefecture (EN):", self.prefecture_en)
        rows.addRow("City/Ward (EN):", self.city_en)
        rows.addRow("Town/Suburb (EN):", self.town_en)

        self.address2 = QLineEdit(); self.address2.setPlaceholderText("e.g. 1 Chome-7-9")
        rows.addRow("Address Line 2:", self.address2)

        mode_layout = QHBoxLayout()
        self.rb_building = QRadioButton("Building")
        self.rb_surrounding = QRadioButton("Surrounding")
        self.rb_building.setChecked(True)
        mode_layout.addWidget(self.rb_building); mode_layout.addWidget(self.rb_surrounding)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.rb_building); self.mode_group.addButton(self.rb_surrounding)

        ov_layout = QHBoxLayout(); ov_layout.setContentsMargins(0, 0, 0, 0); ov_layout.setSpacing(8)
        self.depth_override_cb = QCheckBox(); self.depth_override_cb.setObjectName("depth_override_cb")
        self.depth_override_cb.setToolTip("Enable manual override")
        self.depth_override_cb.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.depth_override_cb.setFixedSize(22, 22)

        self.depth_override_spin = QDoubleSpinBox()
        self.depth_override_spin.setRange(0.0, 100.0); self.depth_override_spin.setDecimals(2)
        self.depth_override_spin.setSingleStep(0.05); self.depth_override_spin.setValue(1.00)
        self.depth_override_spin.setEnabled(False)
        self.depth_override_cb.toggled.connect(self.depth_override_spin.setEnabled)

        ov_layout.addWidget(self.depth_override_cb, 0, Qt.AlignVCenter)
        ov_layout.addWidget(self.depth_override_spin, 1); ov_layout.setStretch(1, 1)
        rows.addRow("Custom Flood Depth (m):", ov_layout)

        fv.addLayout(rows)
        self.submit_btn = QPushButton("Submit")
        self.submit_btn.setAutoDefault(False); self.submit_btn.setDefault(False)
        self.submit_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.submit_btn.setMinimumHeight(40)
        btn_row = QHBoxLayout(); btn_row.setContentsMargins(0, 10, 0, 0); btn_row.addWidget(self.submit_btn)
        fv.addLayout(btn_row)

        top.addWidget(form_panel, 1); self._add_shadow(form_panel)

        log_panel = QWidget(); log_panel.setProperty("panel", "card")
        lv = QVBoxLayout(log_panel); lv.setContentsMargins(16, 16, 16, 16); lv.setSpacing(10)
        log_title = self._make_title("Progress Log")
        lv.addWidget(log_title); TitlePillOverlay(log_panel, log_title)
        lv.addWidget(self._make_hline())
        self.log = QTextEdit(); self.log.setReadOnly(True); self.log.setObjectName("log")
        lv.addWidget(self.log)
        lv.addWidget(self._make_subtitle("Tracks and displays the procedure/details."))
        top.addWidget(log_panel, 1); self._add_shadow(log_panel)

        root.addLayout(top)

        bottom = QHBoxLayout()
        bottom.addWidget(self._make_image_panel("Street-View", "img1_label",
                                               "Google Street View for the entered address."), 0)
        self.cesium_panel = self._make_gpu_panel("Flood Map",
                                                 frame_attr_name="cesium_media_frame",
                                                 placeholder_attr_name="cesium_placeholder",
                                                 desc="3D rendered flood map based on flood depth at the location.")
        bottom.addWidget(self.cesium_panel, 0)
        bottom.addWidget(self._make_image_panel("AI-Generation", "img2_label",
                                                "AI generated image based on flood map and street view image"), 0)
        root.addLayout(bottom)

    def _apply_styles(self):
        p, f = PALETTE, FONTS
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {p.bg}; color: {p.text};
                font-size: {f.base_pt}pt;
                font-family: {to_css_stack(FONT_STACKS.ui)};
            }}
            QWidget[panel="card"] {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 12px;
            }}

            QLabel[role="title"] {{
                font-weight: 700;
                font-size: {f.title_pt}pt;
                padding: 4px 10px;
            }}
            QLabel[role="subtitle"] {{
                color: {p.text_muted};
                font-size: {f.subtitle_pt}pt;
                padding: 6px 6px 6px 6px;
                
            }}

            QLineEdit, QDateEdit, QTimeEdit, QComboBox, QDoubleSpinBox, QTextEdit {{
                background-color: {p.surface_alt};
                border: 1px solid {p.border};
                border-radius: 8px;
                color: {p.text};
                padding: 6px 8px;
                min-height: 28px;
            }}
            QLineEdit:focus, QDateEdit:focus, QTimeEdit:focus, QComboBox:focus,
            QDoubleSpinBox:focus, QTextEdit:focus {{
                border-color: {p.accent};
            }}
            QTextEdit#log {{
                font-family: {to_css_stack(FONT_STACKS.mono)};
                font-size: {max(10, f.base_pt - 1)}pt;
                background-color: {p.surface_alt};
            }}

            QAbstractSpinBox::up-button,
            QAbstractSpinBox::down-button {{ width: 24px; }}

            QPushButton {{
                background-color: {p.accent}; color: #ffffff;
                padding: 8px 14px; border: 1px solid {p.accent};
                border-radius: 8px; font-weight: 600;
            }}
            QPushButton:enabled:hover  {{ background-color: {p.accent_hover}; }}
            QPushButton:enabled:pressed{{ background-color: {p.accent_pressed}; }}
            QPushButton:disabled {{
                background-color: #4a4f58; border-color: #4a4f58; color: #9aa3ad;
            }}

            /* Rim drawn on top of content – give it more breathing room */
            QLabel[role="media"], QFrame[role="media"] {{
                border: 2px dashed {p.border};
                border-radius: 12px;
                background-color: {p.bg};
                padding: 10px;     /* ↑ was 4px */
            }}

            QLabel[role="media"]:hover {{ border: 2px solid {p.accent}; }}
            QFrame[role="media"][hover="true"] {{ border: 2px solid {p.accent}; }}

            QCheckBox, QRadioButton {{ color: {p.text}; }}

            QCheckBox#depth_override_cb {{ padding: 0px; }}
            QCheckBox#depth_override_cb::indicator {{
                width: 18px; height: 18px;
                border: 1px solid {p.border};
                border-radius: 4px;
                background: {p.surface_alt};
            }}
            QCheckBox#depth_override_cb::indicator:hover {{ border-color: {p.accent}; }}
            QCheckBox#depth_override_cb::indicator:checked {{
                background: {p.accent}; border-color: {p.accent}; image: none;
            }}
        """)

    def _postprocess_spinboxes(self):
        for sb in (self.time_edit, self.depth_override_spin, self.date_edit):
            sb.setButtonSymbols(QAbstractSpinBox.UpDownArrows)
            pal = sb.palette()
            pal.setColor(QPalette.ButtonText, QColor(PALETTE.text))
            pal.setColor(QPalette.WindowText, QColor(PALETTE.text))
            sb.setPalette(pal)

    def _init_kakasi(self):
        kks = kakasi()
        kks.setMode("J", "a"); kks.setMode("H", "a"); kks.setMode("K", "a"); kks.setMode("s", True)
        self.converter = kks.getConverter()

    def _make_title(self, text: str) -> QLabel:
        lbl = QLabel(text); lbl.setAlignment(Qt.AlignCenter)
        lbl.setProperty("role", "title"); lbl.setMargin(0); return lbl

    def _make_subtitle(self, text: str) -> QLabel:
        lbl = QLabel(text); lbl.setAlignment(Qt.AlignCenter)
        lbl.setProperty("role", "subtitle"); return lbl
    
    def _install_vertical_title(self):
        # Create the strip with your exact phrasing (can be updated later)
        title_text = "SAFE: Street view based AI Images from Forcast simulations for Evacuation"
        self._title_strip = VerticalTitle(title_text, self, strip_width=96)

        old_layout = self.layout()
        if old_layout is None:
            # If parent UI hasn't set a layout, just make a new H layout
            outer = QHBoxLayout(self)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(0)
            outer.addWidget(self._title_strip)
            # Let consuming code add the rest later
            return

        # Re-wrap existing content into a container so we can prepend the strip
        content = QWidget(self)
        content.setLayout(old_layout)

        outer = QHBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._title_strip)  # fixed width on the left
        outer.addWidget(content, 1)         # your existing UI fills the rest

        self.setLayout(outer)
