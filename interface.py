import sys
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QFormLayout,
    QDateEdit, QLineEdit, QPushButton, QMessageBox
)
from PyQt5.QtCore import QDate, QUrl
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
from pykakasi import kakasi

class AddressForm(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SAFE")
        # Basic dark styling with disabled button appearance
        self.setStyleSheet("""
            QWidget { background: #121212; color: #fff; }
            QLineEdit, QDateEdit {
                background: #1e1e1e;
                border: 1px solid #333;
                color: #fff;
            }
            QPushButton {
                background: #2e7d32;
                color: #fff;
                padding: 6px 12px;
                border: none;
            }
            QPushButton:hover:!disabled { background: #388e3c; }
            QPushButton:disabled {
                background: #555;
                color: #888;
            }
        """
        )

        layout = QFormLayout(self)

        # Date picker
        self.date_edit = QDateEdit(calendarPopup=True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        layout.addRow("Date:", self.date_edit)

        # Postal code input
        self.postal = QLineEdit()
        self.postal.setPlaceholderText("e.g. 271-0076")
        layout.addRow("Postal Code:", self.postal)
        self.postal.editingFinished.connect(self.lookup_postal)
        self.postal.textChanged.connect(self.update_submit_state)

        # Auto-filled address fields (Japanese)
        self.prefecture = QLineEdit(); self.prefecture.setReadOnly(True)
        self.city       = QLineEdit(); self.city.setReadOnly(True)
        self.town       = QLineEdit(); self.town.setReadOnly(True)
        layout.addRow("Prefecture:",  self.prefecture)
        layout.addRow("City/Ward:",   self.city)
        layout.addRow("Town/Suburb:", self.town)

        # Auto-filled address fields (English romanization)
        self.prefecture_en = QLineEdit(); self.prefecture_en.setReadOnly(True)
        self.city_en       = QLineEdit(); self.city_en.setReadOnly(True)
        self.town_en       = QLineEdit(); self.town_en.setReadOnly(True)
        layout.addRow("Prefecture (EN):",  self.prefecture_en)
        layout.addRow("City/Ward (EN):",   self.city_en)
        layout.addRow("Town/Suburb (EN):", self.town_en)

        # Optional free-form continuation
        self.address2 = QLineEdit()
        layout.addRow("Address Line 2:", self.address2)
        self.address2.textChanged.connect(self.update_submit_state)

        # Submit button (disabled until required fields are filled)
        self.submit_btn = QPushButton("Submit")
        self.submit_btn.setEnabled(False)
        layout.addRow(self.submit_btn)
        self.submit_btn.clicked.connect(self.on_submit)

        # Network manager for postal lookup
        self.net = QNetworkAccessManager(self)
        self.net.finished.connect(self.on_api_response)

        # Romanization converter
        kks = kakasi()
        kks.setMode("J", "a")  # Kanji to ascii
        kks.setMode("H", "a")  # Hiragana to ascii
        kks.setMode("K", "a")  # Katakana to ascii
        kks.setMode("s", True)   # add spaced separation
        self.converter = kks.getConverter()

    def update_submit_state(self):
        # Enable submit only if postal code and address2 are non-empty
        has_postal = bool(self.postal.text().strip())
        has_addr2 = bool(self.address2.text().strip())
        self.submit_btn.setEnabled(has_postal and has_addr2)

    def lookup_postal(self):
        code = self.postal.text().strip().replace("-", "")
        if len(code) != 7 or not code.isdigit():
            return
        url = QUrl(f"https://zipcloud.ibsnet.co.jp/api/search?zipcode={code}")
        self.net.get(QNetworkRequest(url))

    def on_api_response(self, reply):
        if reply.error():
            QMessageBox.warning(self, "Lookup Failed", reply.errorString())
            return
        data = json.loads(bytes(reply.readAll()).decode())
        if data.get("status") != 200 or not data.get("results"):
            QMessageBox.information(self, "No Address Found",
                                    "No address matches that postal code.")
            return
        res = data["results"][0]
        # Japanese fields
        jp_pref = res["address1"]
        jp_city = res["address2"]
        jp_town = res["address3"]
        self.prefecture.setText(jp_pref)
        self.city.setText(jp_city)
        self.town.setText(jp_town)
        # English romanization
        self.prefecture_en.setText(self.converter.do(jp_pref))
        self.city_en.setText(self.converter.do(jp_city))
        self.town_en.setText(self.converter.do(jp_town))

    def on_submit(self):
        print("Date:",            self.date_edit.date().toString("yyyy-MM-dd"))
        print("Postal Code:",     self.postal.text())
        print("Prefecture:",      self.prefecture.text())
        print("City/Ward:",       self.city.text())
        print("Town/Suburb:",     self.town.text())
        print("Prefecture (EN):",  self.prefecture_en.text())
        print("City/Ward (EN):",   self.city_en.text())
        print("Town/Suburb (EN):", self.town_en.text())
        print("Address Line 2:",   self.address2.text())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = AddressForm()
    w.show()
    sys.exit(app.exec_())
