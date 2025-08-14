# interface_ui.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QDateEdit, QLineEdit, QPushButton, QTextEdit, QLabel,
    QSizePolicy, QRadioButton, QButtonGroup, QTimeEdit, QComboBox,
    QApplication, QDesktopWidget, QCheckBox, QDoubleSpinBox    # <- add
)
from PyQt5.QtCore import QDate, QTime, Qt
from pykakasi import kakasi
from interface_utility import make_autofill_on_tab
from clickable_label import ClickableLabel

class AddressFormUI(QWidget):
    """
    Builds all static UI (widgets, layouts, styles, kakasi converter).
    """
    def __init__(self):
        # fixed box size for all image panels
        self.boxWidth  = 320
        self.boxHeight = 320
        super().__init__()
        self._build_ui()
        make_autofill_on_tab(self.postal)
        make_autofill_on_tab(self.address2)
        self._apply_styles()
        self._init_kakasi()

    def _make_image_panel(self, title, attr_name, desc):
        panel = QWidget()
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(10, 0, 10, 10)
        pv.setSpacing(5)
        pv.addWidget(self._make_title(title), alignment=Qt.AlignCenter)

        lbl = ClickableLabel(alignment=Qt.AlignCenter)
        lbl.setCursor(Qt.PointingHandCursor)
        lbl.setStyleSheet("border: 2px solid #555;")
        # 1) fix the size of the box
        lbl.setFixedSize(self.boxWidth, self.boxHeight)
        # 2) disallow grow
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        # 3) don't auto-scale content
        lbl.setScaledContents(False)
        # 4) center pixmaps inside
        lbl.setAlignment(Qt.AlignCenter)

        setattr(self, attr_name, lbl)
        pv.addWidget(lbl, alignment=Qt.AlignCenter)
        pv.addWidget(self._make_subtitle(desc), alignment=Qt.AlignCenter)
        
        return panel

    def _build_ui(self):
        # Window
        screen = QDesktopWidget().availableGeometry(self)
        w = int(screen.width() * 0.7)
        h = int(screen.height() * 0.95)
        self.setMinimumSize(w, h)
        self.resize(w, h)
        self.setWindowTitle("SAFE: Street-view AI Images from Forecast Simulations")

        root = QVBoxLayout(self)

        # — Top: form + log —
        top = QHBoxLayout()
        # Form panel
        form_panel = QWidget()
        fv = QVBoxLayout(form_panel)
        fv.setContentsMargins(10,10,10,10)
        fv.setSpacing(10)
        fv.addWidget(self._make_title("Input Form"))

        rows = QFormLayout()
        rows.setHorizontalSpacing(20)
        rows.setVerticalSpacing(15)
        rows.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # Date & Time
        dt_layout = QHBoxLayout()
        self.date_edit = QDateEdit(calendarPopup=True)
        # self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDate(QDate(2025, 7, 10))
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        dt_layout.addWidget(self.date_edit)
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH")
        now = QTime.currentTime()
        # self.time_edit.setTime(QTime(now.hour(),0))
        self.time_edit.setTime(QTime(19, 0))        
        self.time_edit.setMinimumTime(QTime(0,0))
        self.time_edit.setMaximumTime(QTime(23,0))
        dt_layout.addWidget(self.time_edit)
        self.tz_combo = QComboBox()
        self.tz_combo.addItems(["JST","UTC"])
        dt_layout.addWidget(self.tz_combo)
        rows.addRow("Date & Time(Hour):", dt_layout)

        # Postal + address fields
        self.postal = QLineEdit();    self.postal.setPlaceholderText("e.g. 153-0061")
        rows.addRow("Postal Code:", self.postal)
        self.prefecture = QLineEdit(); self.prefecture.setReadOnly(True)
        self.city       = QLineEdit(); self.city.setReadOnly(True)
        self.town       = QLineEdit(); self.town.setReadOnly(True)
        rows.addRow("Prefecture:", self.prefecture)
        rows.addRow("City/Ward:", self.city)
        rows.addRow("Town/Suburb:", self.town)
        self.prefecture_en = QLineEdit(); self.prefecture_en.setReadOnly(True)
        self.city_en       = QLineEdit(); self.city_en.setReadOnly(True)
        self.town_en       = QLineEdit(); self.town_en.setReadOnly(True)
        rows.addRow("Prefecture (EN):", self.prefecture_en)
        rows.addRow("City/Ward (EN):", self.city_en)
        rows.addRow("Town/Suburb (EN):", self.town_en)
        self.address2 = QLineEdit()
        self.address2.setPlaceholderText("e.g. 1 Chome-7-9")
        rows.addRow("Address Line 2:", self.address2)

        # Mode radio buttons
        mode_layout = QHBoxLayout()
        self.rb_building    = QRadioButton("Building")
        self.rb_surrounding = QRadioButton("Surrounding")
        self.rb_building.setChecked(True)
        mode_layout.addWidget(self.rb_building)
        mode_layout.addWidget(self.rb_surrounding)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.rb_building)
        self.mode_group.addButton(self.rb_surrounding)
        # rows.addRow("Perspective Mode:", mode_layout)

        ov_layout = QHBoxLayout()
        self.depth_override_cb = QCheckBox("Override predicted depth (m)")
        self.depth_override_spin = QDoubleSpinBox()
        self.depth_override_spin.setRange(0.0, 100.0)      # meters; adjust if you need more
        self.depth_override_spin.setDecimals(2)
        self.depth_override_spin.setSingleStep(0.05)
        self.depth_override_spin.setValue(1.00)
        self.depth_override_spin.setEnabled(False)         # enabled only when checked
        self.depth_override_cb.toggled.connect(self.depth_override_spin.setEnabled)
        ov_layout.addWidget(self.depth_override_cb)
        ov_layout.addWidget(self.depth_override_spin)
        rows.addRow("Custom Flood Depth:", ov_layout)


        fv.addLayout(rows)
        fv.addStretch(1)
        self.submit_btn = QPushButton("Submit")
        fv.addWidget(self.submit_btn)
        top.addWidget(form_panel, 1)

        # Log panel
        log_panel = QWidget()
        lv = QVBoxLayout(log_panel)
        lv.setContentsMargins(10,10,10,10)
        lv.setSpacing(10)
        lv.addWidget(self._make_title("Progress Log"))
        self.log = QTextEdit(); self.log.setReadOnly(True)
        lv.addWidget(self.log)
        lv.addWidget(self._make_subtitle("Tracks and displays the procedure/details."))
        top.addWidget(log_panel, 1)

        root.addLayout(top)

        # — Bottom: three image panels —
        bottom = QHBoxLayout()
        bottom.addWidget(self._make_image_panel("Street-View", "img1_label",
                        "Google Street View for the entered address."), 0)
        # Cesium placeholder
        self.cesium_panel = QWidget()
        cv = QVBoxLayout(self.cesium_panel)
        cv.setContentsMargins(10,0,10,10)
        cv.setSpacing(5)
        cv.addWidget(self._make_title("3-D Map"), alignment=Qt.AlignCenter)
        self.cesium_placeholder = QLabel("", alignment=Qt.AlignCenter)
        self.cesium_placeholder.setStyleSheet("border:2px solid #555; color:#777;")
        self.cesium_placeholder.setFixedSize(self.boxWidth, self.boxHeight)
        self.cesium_placeholder.setSizePolicy(
            QSizePolicy.Fixed, QSizePolicy.Fixed
        )
        cv.addWidget(self.cesium_placeholder, 0, Qt.AlignCenter)
        cv.addWidget(self._make_subtitle("3D scene of the street-view location"),
                     alignment=Qt.AlignCenter)
        bottom.addWidget(self.cesium_panel, 0)
        bottom.addWidget(self._make_image_panel("AI-Generation", "img2_label",
                        "AI-generated image based on flood depth."), 0)

        root.addLayout(bottom)

    def _apply_styles(self):
        self.setStyleSheet("""
            QWidget { background: #121212; color: #fff; }
            QLineEdit, QDateEdit, QTextEdit {
                background: #1e1e1e; border: 1px solid #333; color: #fff;
            }
            QPushButton {
                background: #2e7d32; color: #fff; padding: 6px 12px; border: none;
            }
            QPushButton:hover:!disabled { background: #388e3c; }
            QPushButton:disabled { background: #555; color: #888; }
            QLabel { background: transparent; color: #fff; }
        """)

    def _init_kakasi(self):
        kks = kakasi()
        kks.setMode("J","a"); kks.setMode("H","a")
        kks.setMode("K","a"); kks.setMode("s", True)
        self.converter = kks.getConverter()

    def _make_title(self, text: str) -> QLabel:
        lbl = QLabel(text); lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("font-weight: bold; font-size: 14pt;")
        return lbl

    def _make_subtitle(self, text: str) -> QLabel:
        lbl = QLabel(text); lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("font-style: italic; font-size: 10pt;")
        return lbl
