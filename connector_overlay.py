# connector_overlay.py
import math
from PyQt5.QtCore import Qt, QPoint, QTimer, QEvent, QRect, QPointF
from PyQt5.QtGui import (
    QPainter, QPen, QColor, QPainterPath, QRegion, QBrush, QRadialGradient
)
from PyQt5.QtWidgets import QWidget


class ConnectorOverlay(QWidget):
    """
    Frameless, always-on-top transparent window that draws animated
    connectors between [street] -> [3D] -> [AI], above everything.
    """

    def __init__(self, host_window):
        flags = (Qt.FramelessWindowHint | Qt.Tool |
                 Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint)
        super().__init__(None, flags)

        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.show_idle = True 

        # host main window we track
        self.host = host_window
        self.host.installEventFilter(self)

        # widgets to connect
        self.w_left = None
        self.w_mid  = None
        self.w_right= None

        # readiness flags
        self.tiles_ready = False
        self.ai_ready    = False

        # behavior
        self.animate_when_waiting_line1 = True   # street -> 3D
        self.animate_when_waiting_line2 = True   # 3D -> AI

        # style
        self.gap_px          = 0
        self.bow_strength    = 0.35   # 0..1: curvature amount
        self.wait_width      = 3.0
        self.ready_width     = 3.5
        self.glow_extra_w1   = 6.0    # outer glow thickness
        self.glow_extra_w2   = 3.0    # inner glow thickness
        self.col_waiting     = QColor(80, 170, 255, 220)
        self.col_ready       = QColor(235, 235, 235, 235)
        self.col_glow        = QColor(140, 200, 255, 70)   # outer glow
        self.col_glow_inner  = QColor(180, 220, 255, 110)  # inner glow

        # animation state
        self._phase      = 0.0   # dash/comet phase
        self._pulse_r    = 0.0   # end pulse radius for "ready" transition
        self._pulse_v    = 0.0   # pulse animation velocity
        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60 FPS
        self._timer.timeout.connect(self._tick)

        # position ourselves over the host
        self._reposition()
        self.show()
    def _draw_idle(self, p: QPainter, path: QPainterPath, base_w: float):
        # dim, static line (no animation)
        col = QColor(self.col_ready)
        col.setAlpha(120)  # faint
        pen = QPen(col)
        pen.setWidthF(base_w)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.drawPath(path)

    # ---------- public API ----------
    def set_widgets(self, left, mid, right):
        self.w_left  = left
        self.w_mid   = mid
        self.w_right = right
        self.update()

    def set_tiles_ready(self, ready: bool):
        was = self.tiles_ready
        self.tiles_ready = bool(ready)
        if self.tiles_ready and not was:
            self._ping_pulse()   # celebrate
        self._update_anim()
        self.update()

    def set_ai_ready(self, ready: bool):
        was = self.ai_ready
        self.ai_ready = bool(ready)
        if self.ai_ready and not was:
            self._ping_pulse()
        self._update_anim()
        self.update()

    def reset(self, quiet=False):
        self.tiles_ready = False
        self.ai_ready = False
        self._pulse_r = 0.0
        self._pulse_v = 0.0
        if quiet:
            # stop waiting animation but keep faint static connectors
            self.animate_when_waiting_line1 = False
            self.animate_when_waiting_line2 = False
            self.show_idle = True
        else:
            # default behavior: show waiting animation when not-ready
            self.animate_when_waiting_line1 = True
            self.animate_when_waiting_line2 = True
            self.show_idle = False
        self._update_anim()
        self.update()

    def resume(self):
        self.animate_when_waiting_line1 = True
        self.animate_when_waiting_line2 = True
        self.show_idle = False
        self._update_anim()
        self.update()


    # ---------- internals ----------
    def eventFilter(self, obj, ev):
        if obj is self.host and ev.type() in (QEvent.Resize, QEvent.Move, QEvent.WindowStateChange):
            self._reposition()
        return False

    def _reposition(self):
        top_left_global = self.host.mapToGlobal(self.host.rect().topLeft())
        self.setGeometry(QRect(top_left_global, self.host.rect().size()))
        self.raise_()

    def _tick(self):
        self._phase = (self._phase + 0.018) % 1.0
        if self._pulse_v != 0.0:
            self._pulse_r += self._pulse_v
            self._pulse_v *= 0.92
            if self._pulse_r < 0.5:
                self._pulse_v = 0.0
                self._pulse_r = 0.0

        # respect the waiting-animation flags here too
        waiting_anim = ((not self.tiles_ready) and self.animate_when_waiting_line1) or \
                    ((not self.ai_ready)    and self.animate_when_waiting_line2)
        need_anim = waiting_anim or (self._pulse_r > 0.0)

        if need_anim:
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()

        self.update()

    def _update_anim(self):
        # only animate if waiting AND that waiting animation is enabled,
        # or if a celebration pulse is still running
        waiting_anim = ((not self.tiles_ready) and self.animate_when_waiting_line1) or \
                    ((not self.ai_ready)    and self.animate_when_waiting_line2)
        need_anim = waiting_anim or (self._pulse_r > 0.0)

        if need_anim and not self._timer.isActive():
            self._timer.start()
        elif not need_anim and self._timer.isActive():
            self._timer.stop()

    def _ping_pulse(self):
        # start a brief pulse at the right end when a link becomes ready
        self._pulse_r = 8.0
        self._pulse_v = -0.45   # shrink over time

    # --- geometry helpers ---
    def _rect_in_overlay(self, w):
        r = QRect(w.mapToGlobal(w.rect().topLeft()), w.rect().size())
        return QRect(self.mapFromGlobal(r.topLeft()), r.size())

    def _anchors(self, wa, wb):
        ra = self._rect_in_overlay(wa)
        rb = self._rect_in_overlay(wb)
        # anchor exactly at the facing edges; +/−0.5 helps crisp pixels on HiDPI
        a = QPointF(ra.right() + 0.5, ra.center().y())
        b = QPointF(rb.left()  - 0.5, rb.center().y())
        return a, b

    def _path(self, a: QPointF, b: QPointF):
        """Cubic bezier with horizontal bow."""
        path = QPainterPath(a)
        dx = (b.x() - a.x()) * self.bow_strength
        c1 = QPointF(a.x() + dx, a.y())
        c2 = QPointF(b.x() - dx, b.y())
        path.cubicTo(c1, c2, b)
        return path

    # --- draw helpers ---
    def _draw_glow(self, p: QPainter, path: QPainterPath, color: QColor, base_w: float):
        pen = QPen(color)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)

        pen.setWidthF(base_w + self.glow_extra_w1)
        p.setPen(pen); p.drawPath(path)

        pen.setColor(self.col_glow_inner)
        pen.setWidthF(base_w + self.glow_extra_w2)
        p.setPen(pen); p.drawPath(path)

    def _draw_waiting(self, p: QPainter, path: QPainterPath, base_w: float):
        # glow
        self._draw_glow(p, path, self.col_glow, base_w)

        # dashed line flowing left->right
        pen = QPen(self.col_waiting)
        pen.setWidthF(base_w)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setStyle(Qt.DashLine)
        pen.setDashPattern([14, 10])
        pen.setDashOffset(-self._phase * 48.0)  # left -> right
        p.setPen(pen)
        p.drawPath(path)

        # comet dot (small bright moving blob)
        t = self._phase  # 0..1 along the path
        pos = path.pointAtPercent(t)
        comet_r = 4.0 + 2.0 * math.sin(self._phase * 2 * math.pi)**2
        g = QRadialGradient(pos, comet_r * 3.0)
        c0 = QColor(self.col_waiting); c0.setAlpha(220)
        c1 = QColor(self.col_waiting); c1.setAlpha(0)
        g.setColorAt(0.0, c0)
        g.setColorAt(1.0, c1)
        p.setBrush(QBrush(g))
        p.setPen(Qt.NoPen)
        p.drawEllipse(pos, comet_r * 2.0, comet_r * 2.0)

    def _draw_ready(self, p: QPainter, path: QPainterPath, base_w: float, end_pt: QPointF):
        # subtle glow
        self._draw_glow(p, path, QColor(255, 255, 255, 60), base_w)

        # solid line
        pen = QPen(self.col_ready)
        pen.setWidthF(base_w)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.drawPath(path)

        # end pulse (brief ring at the right end when transitioned to ready)
        if self._pulse_r > 0.0:
            r = max(0.0, self._pulse_r)
            c = QColor(self.col_ready)
            c.setAlpha(170)
            p.setBrush(Qt.NoBrush)
            ring = QPen(c); ring.setWidthF(2.0)
            p.setPen(ring)
            p.drawEllipse(end_pt, r, r)

    def paintEvent(self, _):
        if not (self.w_left and self.w_mid and self.w_right):
            return

        whole = QRegion(self.rect())

        def box_reg(w):
            # subtract the box *exactly* (no expansion), so the line can
            # render right up to the outer edge without floating away
            r = self._rect_in_overlay(w)
            return QRegion(r)   # no adjusted(+/-)

        clip = whole.subtracted(box_reg(self.w_left))
        clip = clip.subtracted(box_reg(self.w_mid))
        clip = clip.subtracted(box_reg(self.w_right))

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setClipRegion(clip)

        a1, b1 = self._anchors(self.w_left, self.w_mid)
        path1 = self._path(a1, b1)
        if self.tiles_ready:
            self._draw_ready(p, path1, self.ready_width, b1)
        else:
            if self.animate_when_waiting_line1:
                self._draw_waiting(p, path1, self.wait_width)
            elif self.show_idle:
                self._draw_idle(p, path1, self.wait_width)

        a2, b2 = self._anchors(self.w_mid, self.w_right)
        path2 = self._path(a2, b2)
        if self.ai_ready:
            self._draw_ready(p, path2, self.ready_width, b2)
        else:
            if self.animate_when_waiting_line2:
                self._draw_waiting(p, path2, self.wait_width)
            elif self.show_idle:
                self._draw_idle(p, path2, self.wait_width)