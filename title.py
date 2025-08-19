from PyQt5.QtGui import QPainter, QFont, QColor, QLinearGradient, QFontMetrics, QTextOption
from PyQt5.QtCore import Qt, QRect, QSize
from PyQt5.QtWidgets import QWidget, QSizePolicy

def _fit_font_size(text: str, max_rect: QRect, base_font: QFont, wrap_flags=Qt.TextWordWrap,
                   min_px=8, max_px=96) -> QFont:
    """Binary-search a pixel size that fits `text` inside `max_rect`."""
    lo, hi = min_px, max_px
    best = min_px
    while lo <= hi:
        mid = (lo + hi) // 2
        f = QFont(base_font)
        f.setPixelSize(mid)
        fm = QFontMetrics(f)
        br = fm.boundingRect(max_rect, Qt.AlignHCenter | Qt.AlignTop | wrap_flags, text)
        if br.width() <= max_rect.width() and br.height() <= max_rect.height():
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    f = QFont(base_font)
    f.setPixelSize(best)
    return f

class VerticalTitle(QWidget):
    """
    A vertical, full-height title strip with rotated text and gradient background.
    Reads top -> bottom (rotated +90°).
    """
    def __init__(self, text: str, parent=None, strip_width: int = 96):
        super().__init__(parent)
        self._text = text
        self._strip_width = strip_width
        self.setMinimumWidth(strip_width)
        self.setMaximumWidth(strip_width)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def setText(self, text: str):
        self._text = text
        self.update()

    def paintEvent(self, _):
        w, h = self.width(), self.height()
        p = QPainter(self)
        try:
            if not p.isActive():
                return

            p.setRenderHint(QPainter.Antialiasing)
            p.setRenderHint(QPainter.TextAntialiasing)

            # Background gradient (left→right)
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0.0, QColor("#0f172a"))
            grad.setColorAt(1.0, QColor("#1e293b"))
            p.fillRect(self.rect(), grad)

            # Rotate so text reads top→bottom
            p.save()
            p.translate(w, 0)
            p.rotate(90)

            # Padding inside the rotated space
            pad = max(10, int(w * 0.12))
            area = QRect(0, 0, h, w).adjusted(pad, pad, -pad, -pad)

            # Content
            main = "Street2Sea"
            # If you want “Forecast”, update here:
            rest = "Street-view-based AI Visualizations of Predicted Flood Levels to Guide Evacuation"

            # Allocate space: give the headline up to ~40% of height but we’ll fit precisely.
            safe_h_max = int(area.height() * 0.50)
            safe_rect  = QRect(area.left(), area.top(), area.width(), safe_h_max)

            # Fit headline
            base1 = QFont()
            base1.setBold(True)
            f1 = _fit_font_size(main, safe_rect, base1, max_px=max(18, int(w*0.65)))
            p.setFont(f1)
            p.setPen(QColor(245, 247, 250))
            # After fitting, compute exact used height and lock it
            fm1 = QFontMetrics(f1)
            used_h1 = fm1.boundingRect(safe_rect, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, main).height()
            safe_rect.setHeight(used_h1)
            p.drawText(safe_rect, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, main)

            # Remaining area for the subtitle
            gap = max(4, int(w * 0.05))
            rest_rect = QRect(area.left(), safe_rect.bottom() + gap,
                              area.width(), area.bottom() - safe_rect.bottom() - gap)

            # Fit subtitle
            base2 = QFont()
            base2.setLetterSpacing(QFont.PercentageSpacing, 103)
            f2 = _fit_font_size(rest, rest_rect, base2, max_px=max(11, int(w*0.35)))
            p.setFont(f2)
            p.setPen(QColor(225, 229, 234))
            p.drawText(rest_rect, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, rest)

            p.restore()
        finally:
            if p.isActive():
                p.end()