from PyQt5.QtCore import QUrl, pyqtSignal, Qt, QEvent
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage

class DebugPage(QWebEnginePage):
    LEVEL_NAMES = {
        QWebEnginePage.InfoMessageLevel:    "INFO",
        QWebEnginePage.WarningMessageLevel: "WARNING",
        QWebEnginePage.ErrorMessageLevel:   "ERROR",
    }
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        name = self.LEVEL_NAMES.get(level, str(level))
        print(f"[JS:{name}] {sourceID}:{lineNumber} → {message}")

class CesiumViewer(QWebEngineView):
    hoverChanged = pyqtSignal(bool)
    leftClicked  = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        dbg = DebugPage(self)
        self.setPage(dbg)
        dbg.load(QUrl("http://localhost:8000"))

        # help Qt generate hover/move events (some platforms still only fire HoverMove)
        self.setAttribute(Qt.WA_Hover, True)
        self.setMouseTracking(True)

    # Hover state (works across platforms)
    def enterEvent(self, ev):
        self.hoverChanged.emit(True)
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self.hoverChanged.emit(False)
        super().leaveEvent(ev)

    # Fallback for platforms that only deliver HoverMove
    def event(self, ev):
        if ev.type() == QEvent.HoverMove:
            self.hoverChanged.emit(True)
        return super().event(ev)

    # Click pass-through
    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.leftClicked.emit()
        # let Chromium have it too (safe)
        super().mousePressEvent(ev)
