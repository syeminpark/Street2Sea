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


# ---------- visual helpers ----------

class DropShadowCard(QWidget):
    """
    Card with a soft shadow that doesn't interfere with GPU views.
    - _backer: draws the shadowed card shape
    - body:    holds real content (titles, media frame, etc.)
    """
    def __init__(self, blur=24, y=10, alpha=140, parent=None):
        super().__init__(parent)

        # show shadow around edges
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setContentsMargins(0, 0, 0, 0)

        # Backer only for visual shape + shadow
        self._backer = QWidget(self)
        self._backer.setAttribute(Qt.WA_StyledBackground, True)
        self._backer.setAutoFillBackground(True)
        self._backer.setStyleSheet(
            f"background-color: {PALETTE.surface};"
            f"border: 1px solid {PALETTE.border};"
            f"border-radius: 12px;"
        )
        eff = QGraphicsDropShadowEffect(self._backer)
        eff.setBlurRadius(blur)
        eff.setXOffset(0)
        eff.setYOffset(y)
        eff.setColor(QColor(0, 0, 0, alpha))
        self._backer.setGraphicsEffect(eff)

        # Body paints the card surface (kept above backer)
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
    """
    Draws a rounded dark 'pill' behind a title QLabel, aligned to the *text box*
    (not the whole QLabel). Parent this to the visible card surface.
    """
    def __init__(self, parent: QWidget, title_label: QLabel, radius=10):
        super().__init__(parent)
        self._title = title_label
        self._radius = radius
        self.setProperty("role", "overlay")
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # watch both parent & label for changes affecting geometry
        parent.installEventFilter(self)
        title_label.installEventFilter(self)

        self.setGeometry(parent.rect())
        self.raise_()
        self.show()

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
                         QEvent.FontChange, QEvent.StyleChange,
                         QEvent.LayoutRequest):
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
            r = QRectF(self._pill_rect())
            r.adjust(-0.5, -0.5, +0.5, +0.5)
            p.drawRoundedRect(r, self._radius, self._radius)
        finally:
            p.end()




class BrightSpinArrowsStyle(QProxyStyle):
    """
    Transparent stepper area (uses field's navy), thin left divider,
    and light arrows so they pop on dark backgrounds.
    """
    def drawPrimitive(self, element, option, painter, widget=None):
        from PyQt5.QtWidgets import QStyle
        if element in (QStyle.PE_IndicatorSpinUp, QStyle.PE_IndicatorSpinDown):
            r = option.rect
            rr = r.adjusted(0, 0, -1, -1)  # avoid right-edge bleed

            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)

            # Left divider (hairline, same as other borders)
            pen = QPen(QColor(PALETTE.border))
            pen.setCosmetic(True)
            pen.setWidthF(1.0)
            painter.setPen(pen)
            x = rr.left() + 0.5
            painter.drawLine(QLineF(x, rr.top(), x, rr.bottom()))

            # Arrow color: use app palette text (light on navy)
            arrow = QColor(PALETTE.text) if (option.state & QStyle.State_Enabled) \
                    else QColor(255, 255, 255, 120)

            # Arrow area (auto scales; not squished)
            m = max(2, min(5, int(min(rr.width(), rr.height()) * 0.14)))
            ar = rr.adjusted(m, m, -m, -m)

            if element == QStyle.PE_IndicatorSpinUp:
                tri = QPolygon([
                    QPoint(ar.center().x(), ar.top()),
                    QPoint(ar.right(),      ar.bottom()),
                    QPoint(ar.left(),       ar.bottom()),
                ])
            else:
                tri = QPolygon([
                    QPoint(ar.left(),       ar.top()),
                    QPoint(ar.right(),      ar.top()),
                    QPoint(ar.center().x(), ar.bottom()),
                ])

            painter.setPen(Qt.NoPen)
            painter.setBrush(arrow)
            painter.drawPolygon(tri)

            painter.restore()
            return

        return super().drawPrimitive(element, option, painter, widget)



# ---------- main UI ----------

class AddressFormUI(QWidget):
    """
    Builds all static UI (widgets, layouts, styles, kakasi converter).
    """

    def __init__(self):
        # fixed box size for all image panels
        self.boxWidth = 512
        self.boxHeight = 512
        super().__init__()

        # Helps avoid native macOS quirks when using QSS on spinboxes
        QApplication.setStyle(QStyleFactory.create("Fusion"))
        # Wrap the current style so our arrows render reliably
        QApplication.setStyle(BrightSpinArrowsStyle(QApplication.style()))

        self._build_ui()
        make_autofill_on_tab(self.postal)
        make_autofill_on_tab(self.address2)
        self._apply_styles()
        self._postprocess_spinboxes()
        self._init_kakasi()

    # ----- small helpers -----

    def _add_shadow(self, w, blur=24, y=10, alpha=140):
        eff = QGraphicsDropShadowEffect(self)
        eff.setBlurRadius(blur)
        eff.setXOffset(0)
        eff.setYOffset(y)
        eff.setColor(QColor(0, 0, 0, alpha))
        w.setGraphicsEffect(eff)

    def _make_hline(self) -> QWidget:
        spacer = QWidget()
        spacer.setFixedHeight(6)
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        spacer.setAttribute(Qt.WA_StyledBackground, False)
        return spacer

    def _make_image_panel(self, title_text, attr_name, desc):
        panel = QWidget()
        panel.setProperty("panel", "card")
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(10, 8, 10, 10)
        pv.setSpacing(5)

        title = self._make_title(title_text)
        pv.addWidget(title, alignment=Qt.AlignCenter)
        TitlePillOverlay(panel, title)

        lbl = ClickableLabel(alignment=Qt.AlignCenter)
        lbl.setCursor(Qt.PointingHandCursor)
        lbl.setFixedSize(self.boxWidth, self.boxHeight)
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        lbl.setScaledContents(False)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setProperty("role", "media")
        lbl.setMargin(2)  # METHOD 1: ensure pixmap stays inside the border

        setattr(self, attr_name, lbl)
        pv.addWidget(lbl, alignment=Qt.AlignCenter)
        pv.addWidget(self._make_subtitle(desc), alignment=Qt.AlignCenter)

        self._add_shadow(panel, blur=20, y=8, alpha=120)
        return panel

    def _make_gpu_panel(self, title_text, frame_attr_name, placeholder_attr_name, desc):
        wrapper = DropShadowCard(blur=20, y=8, alpha=120)

        v = QVBoxLayout(wrapper.body)
        v.setContentsMargins(10, 8, 10, 10)
        v.setSpacing(5)

        title = self._make_title(title_text)
        v.addWidget(title, alignment=Qt.AlignCenter)
        TitlePillOverlay(wrapper.body, title)

        frame = QFrame()
        frame.setProperty("role", "media")
        frame.setFixedSize(self.boxWidth, self.boxHeight)
        frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        frame.setAttribute(Qt.WA_StyledBackground, True)
        frame.setAutoFillBackground(True)
        # Keep a border & padding here too so it matches the global QSS and
        # guarantees the hover outline remains visible above content.
        frame.setStyleSheet(
            f"background-color: {PALETTE.bg};"
            f"border: 2px dashed {PALETTE.border};"
            f"border-radius: 12px;"
            f"padding: 2px;"
        )

        fl = QVBoxLayout(frame)
        fl.setContentsMargins(2, 2, 2, 2)  # METHOD 1: content offset from the border
        fl.setSpacing(0)

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

    # ----- build UI -----

    def _build_ui(self):
        # Window
        screen = QDesktopWidget().availableGeometry(self)
        w = int(screen.width() * 0.7)
        h = int(screen.height() * 0.95)
        self.setMinimumSize(w, h)
        self.resize(w, h)
        self.setWindowTitle("SAFE: Street-view AI Images from Forecast Simulations")

        root = QVBoxLayout(self)

        # Top row: form + log
        top = QHBoxLayout()

        # Form panel
        form_panel = QWidget()
        form_panel.setProperty("panel", "card")
        fv = QVBoxLayout(form_panel)
        fv.setContentsMargins(16, 16, 16, 16)
        fv.setSpacing(10)

        form_title = self._make_title("Input Form")
        fv.addWidget(form_title)
        TitlePillOverlay(form_panel, form_title)
        fv.addWidget(self._make_hline())

        rows = QFormLayout()
        rows.setHorizontalSpacing(20)
        rows.setVerticalSpacing(16)
        rows.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        rows.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Date & Time
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

        # Postal + address fields
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

        # (kept for future) Mode radios
        mode_layout = QHBoxLayout()
        self.rb_building = QRadioButton("Building")
        self.rb_surrounding = QRadioButton("Surrounding")
        self.rb_building.setChecked(True)
        mode_layout.addWidget(self.rb_building)
        mode_layout.addWidget(self.rb_surrounding)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.rb_building)
        self.mode_group.addButton(self.rb_surrounding)

        # Custom flood depth
        ov_layout = QHBoxLayout()
        ov_layout.setContentsMargins(0, 0, 0, 0)
        ov_layout.setSpacing(8)

        self.depth_override_cb = QCheckBox()
        self.depth_override_cb.setObjectName("depth_override_cb")
        self.depth_override_cb.setToolTip("Enable manual override")

        # keep the checkbox compact
        self.depth_override_cb.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.depth_override_cb.setFixedSize(22, 22)  # outer clickable area

        self.depth_override_spin = QDoubleSpinBox()
        self.depth_override_spin.setRange(0.0, 100.0)
        self.depth_override_spin.setDecimals(2)
        self.depth_override_spin.setSingleStep(0.05)
        self.depth_override_spin.setValue(1.00)
        self.depth_override_spin.setEnabled(False)

        self.depth_override_cb.toggled.connect(self.depth_override_spin.setEnabled)

        ov_layout.addWidget(self.depth_override_cb, 0, Qt.AlignVCenter)
        ov_layout.addWidget(self.depth_override_spin, 1)   # let the spinbox take the width
        ov_layout.setStretch(1, 1)

        rows.addRow("Custom Flood Depth (m):", ov_layout)

        fv.addLayout(rows)
        self.submit_btn = QPushButton("Submit")
        self.submit_btn.setAutoDefault(False)
        self.submit_btn.setDefault(False)
        self.submit_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.submit_btn.setMinimumHeight(40)  # stronger than before

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 10, 0, 0)   # <- 10px gap above the button
        btn_row.addWidget(self.submit_btn)

        fv.addLayout(btn_row)

     
        top.addWidget(form_panel, 1)
        self._add_shadow(form_panel)

        # Log panel
        log_panel = QWidget()
        log_panel.setProperty("panel", "card")
        lv = QVBoxLayout(log_panel)
        lv.setContentsMargins(16, 16, 16, 16)
        lv.setSpacing(10)

        log_title = self._make_title("Progress Log")
        lv.addWidget(log_title)
        TitlePillOverlay(log_panel, log_title)
        lv.addWidget(self._make_hline())

        self.log = QTextEdit(); self.log.setReadOnly(True)
        self.log.setObjectName("log")
        lv.addWidget(self.log)
        lv.addWidget(self._make_subtitle("Tracks and displays the procedure/details."))
        top.addWidget(log_panel, 1)
        self._add_shadow(log_panel)

        root.addLayout(top)

        # Bottom row: three panels
        bottom = QHBoxLayout()

        bottom.addWidget(
            self._make_image_panel(
                "Street-View", "img1_label", "Google Street View for the entered address."
            ),
            0,
        )

        self.cesium_panel = self._make_gpu_panel(
            "3-D Map",
            frame_attr_name="cesium_media_frame",
            placeholder_attr_name="cesium_placeholder",
            desc="3D scene of the street-view location",
        )
        bottom.addWidget(self.cesium_panel, 0)

        bottom.addWidget(
            self._make_image_panel(
                "AI-Generation", "img2_label", "AI-generated image based on flood depth."
            ),
            0,
        )

        root.addLayout(bottom)

    # ----- styles -----

    def _apply_styles(self):
        p, f = PALETTE, FONTS
        self.setStyleSheet(f"""
            /* App base */
            QWidget {{
                background-color: {p.bg}; color: {p.text};
                font-size: {f.base_pt}pt;
                font-family: {to_css_stack(FONT_STACKS.ui)};
            }}
            
            /* Standard cards (non-GPU) */
            QWidget[panel="card"] {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 12px;
            }}

            /* Titles & subtitles */
            QLabel[role="title"] {{
                font-weight: 700;
                font-size: {f.title_pt}pt;
                padding: 4px 10px;
            }}
            QLabel[role="subtitle"] {{
                color: {p.text_muted};
                font-size: {f.subtitle_pt}pt;
                padding: 2px 6px 8px 6px;
            }}

            /* Inputs */
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

           /* ---- Spinboxes / time edits: white steppers ---- */

QAbstractSpinBox::up-button,
QAbstractSpinBox::down-button {{
    width: 24px;
}}
            /* Buttons */
            QPushButton {{
                background-color: {p.accent};
                color: #ffffff;
                padding: 8px 14px;
                border: 1px solid {p.accent};
                border-radius: 8px;
                font-weight: 600;
            }}
            QPushButton:enabled:hover  {{ background-color: {p.accent_hover}; }}
            QPushButton:enabled:pressed{{ background-color: {p.accent_pressed}; }}
            QPushButton:disabled {{
                background-color: #4a4f58;
                border-color: #4a4f58;
                color: #9aa3ad;
            }}

            /* Media boxes (Street, Cesium frame, AI) */
            QLabel[role="media"], QFrame[role="media"] {{
                border: 2px dashed {p.border};
                border-radius: 12px;
                background-color: {p.bg};
                padding: 2px; /* METHOD 1: keep content away from the border */
            }}
            QLabel[role="media"]:hover, QFrame[role="media"]:hover {{
                border: 2px solid {p.accent}; /* METHOD 1: visible hover stroke */
            }}

            /* Small controls */
            QCheckBox, QRadioButton {{ color: {p.text}; }}
            /* Bigger, clearer checkbox just for this row */
QCheckBox#depth_override_cb {{
    padding: 0px;
}}
QCheckBox#depth_override_cb::indicator {{
    width: 18px; height: 18px;
    border: 1px solid {p.border};
    border-radius: 4px;
    background: {p.surface_alt};
}}
QCheckBox#depth_override_cb::indicator:hover {{
    border-color: {p.accent};
}}
QCheckBox#depth_override_cb::indicator:checked {{
    background: {p.accent};
    border-color: {p.accent};
    image: none; /* keep it a solid fill, no platform checkmark glyph */
}}

        """)

    # ----- spinbox tweaks (palette & symbols) -----

    def _postprocess_spinboxes(self):
        for sb in (self.time_edit, self.depth_override_spin, self.date_edit):
            sb.setButtonSymbols(QAbstractSpinBox.UpDownArrows)
            pal = sb.palette()
            pal.setColor(QPalette.ButtonText, QColor(PALETTE.text))   # light arrows
            pal.setColor(QPalette.WindowText, QColor(PALETTE.text))
            sb.setPalette(pal)


    # ----- kakasi -----

    def _init_kakasi(self):
        kks = kakasi()
        kks.setMode("J", "a")
        kks.setMode("H", "a")
        kks.setMode("K", "a")
        kks.setMode("s", True)
        self.converter = kks.getConverter()

    # ----- label makers -----

    def _make_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setProperty("role", "title")
        lbl.setMargin(0)
        return lbl

    def _make_subtitle(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setProperty("role", "subtitle")
        return lbl
