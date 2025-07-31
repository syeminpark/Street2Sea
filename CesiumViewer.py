# cesium_viewer.py
from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage

class DebugPage(QWebEnginePage):
    LEVEL_NAMES = {
        QWebEnginePage.InfoMessageLevel:    "INFO",
        QWebEnginePage.WarningMessageLevel: "WARNING",
        QWebEnginePage.ErrorMessageLevel:   "ERROR",
    }

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        # map the integer level to something human-readable
        name = self.LEVEL_NAMES.get(level, str(level))
        print(f"[JS:{name}] {sourceID}:{lineNumber} → {message}")

class CesiumViewer(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        # replace the default page with our debug page
        dbg = DebugPage(self)
        self.setPage(dbg)
        dbg.load(QUrl("http://localhost:8000"))
