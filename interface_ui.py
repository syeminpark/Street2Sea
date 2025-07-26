# interface_ui.py

import json
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QDateEdit, QLineEdit, QPushButton, QTextEdit, QLabel,
    QSizePolicy, QRadioButton, QButtonGroup, QTimeEdit
)
from PyQt5.QtCore import QDate, QTime, Qt
from pykakasi import kakasi


class AddressFormUI(QWidget):
    """
    Base class: builds all the static UI (widgets, layouts, styles, kakasi converter),
    but does not hook up any signals or network logic.
    Now includes a mode checkbox to choose between 'Building' or 'Surrounding' views,
    and a Date & Time picker that only allows selecting the hour.
    """
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._apply_styles()
        self._init_kakasi()

    def _build_ui(self):
        # Window setup
        self.setMinimumSize(900, 900)
        self.setWindowTitle("SAFE: Street‑view AI Images from Forecast Simulations")
        root = QVBoxLayout(self)

        # === Top row: form + log ===
        top = QHBoxLayout()

        # — Form panel —
        form_panel = QWidget()
        fv = QVBoxLayout(form_panel)
        fv.setContentsMargins(10, 10, 10, 10)
        fv.setSpacing(10)
        fv.addWidget(self._make_title("User Input Form"))

        rows = QFormLayout()
        rows.setHorizontalSpacing(20)
        rows.setVerticalSpacing(15)

        # Date & Time (hour only)
        datetime_layout = QHBoxLayout()
        self.date_edit = QDateEdit(calendarPopup=True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        datetime_layout.addWidget(self.date_edit)

        self.time_edit = QTimeEdit()
        # Display only hours
        self.time_edit.setDisplayFormat("HH")
        now = QTime.currentTime()
        # Initialize time to current hour, zero minutes
        self.time_edit.setTime(QTime(now.hour(), 0))
        # Restrict range to whole hours
        self.time_edit.setMinimumTime(QTime(0, 0))
        self.time_edit.setMaximumTime(QTime(23, 0))
        datetime_layout.addWidget(self.time_edit)

        rows.addRow("Date & Time(Hour):", datetime_layout)

        # Postal code
        self.postal = QLineEdit()
        self.postal.setPlaceholderText("e.g. 271-0076")
        rows.addRow("Postal Code:", self.postal)

        # Japanese address fields
        self.prefecture = QLineEdit();   self.prefecture.setReadOnly(True)
        self.city       = QLineEdit();   self.city.setReadOnly(True)
        self.town       = QLineEdit();   self.town.setReadOnly(True)
        rows.addRow("Prefecture:",  self.prefecture)
        rows.addRow("City/Ward:",   self.city)
        rows.addRow("Town/Suburb:", self.town)

        # English romanization
        self.prefecture_en = QLineEdit(); self.prefecture_en.setReadOnly(True)
        self.city_en       = QLineEdit(); self.city_en.setReadOnly(True)
        self.town_en       = QLineEdit(); self.town_en.setReadOnly(True)
        rows.addRow("Prefecture (EN):",  self.prefecture_en)
        rows.addRow("City/Ward (EN):",   self.city_en)
        rows.addRow("Town/Suburb (EN):", self.town_en)

        # Address Line 2
        self.address2 = QLineEdit()
        self.address2.setPlaceholderText("e.g. 27‑2 or Bear Pond Espresso")
        rows.addRow("Address Line 2:", self.address2)

        # Mode selection: Building vs Surrounding
        mode_layout = QHBoxLayout()
        self.rb_building    = QRadioButton("Building")
        self.rb_surrounding = QRadioButton("Surrounding")
        self.rb_building.setChecked(True)
        mode_layout.addWidget(self.rb_building)
        mode_layout.addWidget(self.rb_surrounding)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.rb_building)
        self.mode_group.addButton(self.rb_surrounding)
        rows.addRow("Perspective Mode:", mode_layout)

        # Finish form panel
        fv.addLayout(rows)
        fv.addStretch(1)
        self.submit_btn = QPushButton("Submit")
        fv.addWidget(self.submit_btn)
        top.addWidget(form_panel, 1)

        # — Log panel —
        log_panel = QWidget()
        lv = QVBoxLayout(log_panel)
        lv.setContentsMargins(10, 10, 10, 10)
        lv.setSpacing(10)
        lv.addWidget(self._make_title("Progress Log"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        lv.addWidget(self.log)
        lv.addWidget(self._make_subtitle("Tracks and displays the procedure/details."))
        top.addWidget(log_panel, 1)

        root.addLayout(top)

        # === Bottom row: image panels ===
        bottom = QHBoxLayout()
        for title, attr, desc in (
            ("Street‑View",  "img1_label", "Google Street View for the entered address."),
            ("AI‑Generated", "img2_label", "AI‑generated image based on flood depth."),
        ):
            panel = QWidget()
            pv = QVBoxLayout(panel)
            pv.setContentsMargins(10, 0, 10, 10)
            pv.setSpacing(5)
            pv.addWidget(self._make_title(title))
            lbl = QLabel(alignment=Qt.AlignCenter)
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            lbl.setScaledContents(True)
            lbl.setStyleSheet("border: 2px solid #555;")
            setattr(self, attr, lbl)
            pv.addWidget(lbl)
            pv.addWidget(self._make_subtitle(desc))
            bottom.addWidget(panel, 1)

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
            QPushButton:disabled {
                background: #555; color: #888;
            }
            QLabel {
                background: transparent; color: #fff;
            }
        """)

    def _init_kakasi(self):
        kks = kakasi()
        kks.setMode("J", "a")
        kks.setMode("H", "a")
        kks.setMode("K", "a")
        kks.setMode("s", True)
        self.converter = kks.getConverter()

    def _make_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("font-weight: bold; font-size: 14pt;")
        return lbl

    def _make_subtitle(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("font-style: italic; font-size: 10pt;")
        return lbl
