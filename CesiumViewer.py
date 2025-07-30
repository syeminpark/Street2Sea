# cesium_viewer.py
from PyQt5.QtCore             import QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView   # pip install PyQtWebEngine

class CesiumViewer(QWebEngineView):
    """
    A drop‑in widget that shows http://localhost:8000
    (served by server.js that node_runner.py launches).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setUrl(QUrl("http://localhost:8000"))   # change port/path if needed


