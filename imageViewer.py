# image_viewer.py
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QGraphicsView, QGraphicsScene
from PyQt5.QtWidgets import QGraphicsPixmapItem, QApplication
from PyQt5.QtGui import QPixmap, QPainter
from PyQt5.QtCore import Qt, QRectF

class ImageViewerDialog(QDialog):
    def __init__(self, title="Image", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.view = QGraphicsView(self)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)

        self.scene = QGraphicsScene(self)
        self.view.setScene(self.scene)
        self.pix_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pix_item)

        lay = QVBoxLayout(self)
        lay.addWidget(self.view)

        # size ~80% of screen
        screen = QApplication.desktop().availableGeometry(self)
        self.resize(int(screen.width()*0.8), int(screen.height()*0.8))

        self._zoom = 0
        self._fit_on_show = True

    def set_pixmap(self, pix: QPixmap):
        if pix.isNull():
            return
        self.pix_item.setPixmap(pix)
        w, h = float(pix.width()), float(pix.height())
        # Use QRectF or the 4-float overload
        self.scene.setSceneRect(QRectF(0.0, 0.0, w, h))
        # or: self.scene.setSceneRect(0.0, 0.0, w, h)
        self._zoom = 0
        self._fit_on_show = True
        self._fit_in_view()

    def wheelEvent(self, e):
        if not self.pix_item.pixmap().isNull():
            factor = 1.25 if e.angleDelta().y() > 0 else 0.8
            self.view.scale(factor, factor)
            self._zoom += 1 if factor > 1 else -1
            self._fit_on_show = False

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Escape,):
            self.close()
        elif e.key() == Qt.Key_0:       # reset + fit
            self._fit_in_view()
        elif e.key() == Qt.Key_F:       # fullscreen toggle
            self.setWindowState(self.windowState() ^ Qt.WindowFullScreen)
        else:
            super().keyPressEvent(e)

    def mouseDoubleClickEvent(self, e):
        self._fit_in_view()
        self._fit_on_show = True
        super().mouseDoubleClickEvent(e)

    def showEvent(self, e):
        super().showEvent(e)
        if self._fit_on_show:
            self._fit_in_view()

    def _fit_in_view(self):
        self.view.fitInView(self.pix_item, Qt.KeepAspectRatio)
