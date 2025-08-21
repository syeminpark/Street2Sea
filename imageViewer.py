# image_viewer.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QToolButton,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QApplication, QShortcut, QMenu
)
from PyQt5.QtGui import QPixmap, QPainter, QKeySequence
from PyQt5.QtCore import Qt, QRectF, QEvent, QPoint

class _TitleBar(QWidget):
    def __init__(self, host, title):
        super().__init__(host)
        self._host = host
        self.setFixedHeight(34)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4); lay.setSpacing(8)
        self.lbl = QLabel(title, self)
        self.lbl.setStyleSheet("font-weight:600;")
        self.btn_close = QToolButton(self); self.btn_close.setText("✕")
        self.btn_close.setAutoRaise(True)
        self.btn_close.setToolTip("Close")
        self.btn_close.clicked.connect(host.close)
        lay.addWidget(self.lbl); lay.addStretch(1); lay.addWidget(self.btn_close)
        self._dragOffset = None

    # drag window by the custom title bar
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._dragOffset = e.globalPos() - self._host.frameGeometry().topLeft()
            e.accept()
    def mouseMoveEvent(self, e):
        if (e.buttons() & Qt.LeftButton) and self._dragOffset:
            self._host.move(e.globalPos() - self._dragOffset); e.accept()
    def mouseReleaseEvent(self, e):
        self._dragOffset = None
        super().mouseReleaseEvent(e)

class ImageViewerDialog(QDialog):
    def __init__(self, title="Image", parent=None):
        super().__init__(parent)
        # ← Frameless avoids macOS sharing badge replacing the close button
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.titlebar = _TitleBar(self, title)

        self.view = QGraphicsView(self)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setFocusPolicy(Qt.ClickFocus)
        self.view.installEventFilter(self)
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._show_ctx_menu)

        self.scene = QGraphicsScene(self); self.view.setScene(self.scene)
        self.pix_item = QGraphicsPixmapItem(); self.scene.addItem(self.pix_item)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(1, 1, 1, 1); lay.setSpacing(0)
        lay.addWidget(self.titlebar)     # custom title bar (with Close)
        lay.addWidget(self.view)

        # size ~80% of screen
        screen = QApplication.desktop().availableGeometry(self)
        self.resize(int(screen.width()*0.8), int(screen.height()*0.8))

        self._zoom = 0
        self._fit_on_show = True

        # App-level “panic” shortcuts (work even if the view has focus)
        for seq in ("Escape", "Ctrl+W", "Meta+W"):
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(self.close)

        # simple styling (optional)
        self.setStyleSheet("""
            QDialog { background: #1e1f24; border: 1px solid #2b2c31; border-radius: 10px; }
            QGraphicsView { background: #0f1013; border: none; }
        """)

    # make Esc work even when QGraphicsView is focused
    def eventFilter(self, obj, event):
        if obj is self.view and event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.close(); return True
        return super().eventFilter(obj, event)

    def _show_ctx_menu(self, pos: QPoint):
        menu = QMenu(self.view)
        act_fit = menu.addAction("Fit image"); act_close = menu.addAction("Close")
        chosen = menu.exec_(self.view.mapToGlobal(pos))
        if chosen == act_fit: self._fit_in_view()
        elif chosen == act_close: self.close()

    def set_pixmap(self, pix: QPixmap):
        if pix.isNull(): return
        self.pix_item.setPixmap(pix)
        w, h = float(pix.width()), float(pix.height())
        self.scene.setSceneRect(QRectF(0.0, 0.0, w, h))
        self._zoom = 0; self._fit_on_show = True; self._fit_in_view()

    def wheelEvent(self, e):
        if not self.pix_item.pixmap().isNull():
            factor = 1.25 if e.angleDelta().y() > 0 else 0.8
            self.view.scale(factor, factor)
            self._zoom += 1 if factor > 1 else -1
            self._fit_on_show = False

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_0:
            self._fit_in_view()
        elif e.key() == Qt.Key_F:
            self.showMaximized()   # avoid native full screen during sharing
        else:
            super().keyPressEvent(e)

    def showEvent(self, e):
        super().showEvent(e)
        self.raise_(); self.activateWindow()
        if self._fit_on_show: self._fit_in_view()

    def _fit_in_view(self):
        self.view.fitInView(self.pix_item, Qt.KeepAspectRatio)
