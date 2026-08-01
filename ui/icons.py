"""Vector-drawn icon set (no emoji, no external assets)."""

from __future__ import annotations

import math
from typing import Callable, Dict, Tuple

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QLabel, QWidget

from ui.theme import ACCENT, ERROR, SUCCESS


_ICON_CACHE: Dict[Tuple[str, str, int], QPixmap] = {}


def _icon(name: str, color: str, size: int = 18) -> QPixmap:
    key = (name, color, size)
    cached = _ICON_CACHE.get(key)
    if cached is not None:
        return cached
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(max(1.4, size * 0.08))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    pad = size * 0.1
    r = QRectF(pad, pad, size - 2 * pad, size - 2 * pad)
    draw = _ICON_DRAW.get(name)
    if draw:
        draw(p, r)
    p.end()
    _ICON_CACHE[key] = pm
    return pm


def _icon_label(name: str, color: str, size: int = 16) -> QLabel:
    lab = QLabel()
    lab.setPixmap(_icon(name, color, size))
    lab.setFixedSize(size, size)
    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lab


def _apply_shadow(widget: QWidget, blur: int = 22, y: int = 3, alpha: int = 70) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)


def _idot(p: QPainter, r: QRectF) -> None:
    c = r.center()
    p.drawLine(QPointF(c.x() - r.width() * 0.08, c.y()), QPointF(c.x() - r.width() * 0.08, c.y()))
    p.drawLine(QPointF(c.x() + r.width() * 0.08, c.y()), QPointF(c.x() + r.width() * 0.08, c.y()))


def _ihome(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx = x + w / 2
    p.drawLine(QPointF(x, y + h * 0.48), QPointF(cx, y + h * 0.14))
    p.drawLine(QPointF(cx, y + h * 0.14), QPointF(x + w, y + h * 0.48))
    path = QPainterPath()
    path.moveTo(x + w * 0.22, y + h * 0.42)
    path.lineTo(x + w * 0.22, y + h * 0.9)
    path.lineTo(x + w * 0.78, y + h * 0.9)
    path.lineTo(x + w * 0.78, y + h * 0.42)
    p.drawPath(path)
    p.drawLine(QPointF(x + w * 0.44, y + h * 0.9), QPointF(x + w * 0.44, y + h * 0.66))
    p.drawLine(QPointF(x + w * 0.56, y + h * 0.66), QPointF(x + w * 0.56, y + h * 0.9))


def _ipackage(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx = x + w / 2
    top = QPainterPath()
    top.moveTo(x + w * 0.15, y + h * 0.3)
    top.lineTo(cx, y + h * 0.12)
    top.lineTo(x + w * 0.85, y + h * 0.3)
    top.lineTo(cx, y + h * 0.48)
    top.closeSubpath()
    p.drawPath(top)
    left = QPainterPath()
    left.moveTo(x + w * 0.15, y + h * 0.3)
    left.lineTo(x + w * 0.15, y + h * 0.8)
    left.lineTo(cx, y + h * 0.98)
    left.lineTo(cx, y + h * 0.48)
    left.closeSubpath()
    p.drawPath(left)
    right = QPainterPath()
    right.moveTo(x + w * 0.85, y + h * 0.3)
    right.lineTo(x + w * 0.85, y + h * 0.8)
    right.lineTo(cx, y + h * 0.98)
    right.lineTo(cx, y + h * 0.48)
    right.closeSubpath()
    p.drawPath(right)


def _ichart(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    p.drawLine(QPointF(x + w * 0.08, y + h * 0.92), QPointF(x + w * 0.92, y + h * 0.92))
    p.drawLine(QPointF(x + w * 0.25, y + h * 0.92), QPointF(x + w * 0.25, y + h * 0.34))
    p.drawLine(QPointF(x + w * 0.5, y + h * 0.92), QPointF(x + w * 0.5, y + h * 0.6))
    p.drawLine(QPointF(x + w * 0.75, y + h * 0.92), QPointF(x + w * 0.75, y + h * 0.14))


def _iscale(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx = x + w / 2
    p.drawLine(QPointF(cx, y + h * 0.16), QPointF(cx, y + h * 0.82))
    p.drawLine(QPointF(x + w * 0.16, y + h * 0.9), QPointF(x + w * 0.84, y + h * 0.9))
    p.drawLine(QPointF(x + w * 0.1, y + h * 0.2), QPointF(x + w * 0.9, y + h * 0.2))
    p.drawLine(QPointF(x + w * 0.2, y + h * 0.2), QPointF(x + w * 0.2, y + h * 0.5))
    p.drawLine(QPointF(x + w * 0.08, y + h * 0.5), QPointF(x + w * 0.32, y + h * 0.5))
    p.drawLine(QPointF(x + w * 0.8, y + h * 0.2), QPointF(x + w * 0.8, y + h * 0.5))
    p.drawLine(QPointF(x + w * 0.68, y + h * 0.5), QPointF(x + w * 0.92, y + h * 0.5))


def _ibulb(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx = x + w / 2
    p.drawEllipse(QPointF(cx, y + h * 0.3), w * 0.24, h * 0.24)
    p.drawLine(QPointF(cx - w * 0.09, y + h * 0.54), QPointF(cx - w * 0.09, y + h * 0.62))
    p.drawLine(QPointF(cx + w * 0.09, y + h * 0.54), QPointF(cx + w * 0.09, y + h * 0.62))
    p.drawLine(QPointF(cx - w * 0.09, y + h * 0.62), QPointF(cx - w * 0.15, y + h * 0.78))
    p.drawLine(QPointF(cx + w * 0.09, y + h * 0.62), QPointF(cx + w * 0.15, y + h * 0.78))
    p.drawLine(QPointF(cx - w * 0.15, y + h * 0.78), QPointF(cx + w * 0.15, y + h * 0.78))
    p.drawLine(QPointF(x + w * 0.42, y + h * 0.3), QPointF(x + w * 0.3, y + h * 0.24))
    p.drawLine(QPointF(x + w * 0.42, y + h * 0.16), QPointF(x + w * 0.3, y + h * 0.1))
    p.drawLine(QPointF(x + w * 0.58, y + h * 0.3), QPointF(x + w * 0.7, y + h * 0.24))
    p.drawLine(QPointF(x + w * 0.58, y + h * 0.16), QPointF(x + w * 0.7, y + h * 0.1))


def _itrophy(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx = x + w / 2
    body = QPainterPath()
    body.moveTo(x + w * 0.2, y + h * 0.14)
    body.lineTo(x + w * 0.2, y + h * 0.44)
    body.lineTo(x + w * 0.36, y + h * 0.58)
    body.lineTo(x + w * 0.64, y + h * 0.58)
    body.lineTo(x + w * 0.8, y + h * 0.44)
    body.lineTo(x + w * 0.8, y + h * 0.14)
    body.lineTo(x + w * 0.2, y + h * 0.14)
    p.drawPath(body)
    p.drawLine(QPointF(x + w * 0.16, y + h * 0.14), QPointF(x + w * 0.84, y + h * 0.14))
    handle = QPainterPath()
    handle.moveTo(x + w * 0.2, y + h * 0.22)
    handle.cubicTo(x + w * 0.02, y + h * 0.28, x + w * 0.02, y + h * 0.5, x + w * 0.2, y + h * 0.56)
    handle.moveTo(x + w * 0.8, y + h * 0.22)
    handle.cubicTo(x + w * 0.98, y + h * 0.28, x + w * 0.98, y + h * 0.5, x + w * 0.8, y + h * 0.56)
    p.drawPath(handle)
    p.drawLine(QPointF(cx, y + h * 0.58), QPointF(cx, y + h * 0.74))
    p.drawLine(QPointF(x + w * 0.28, y + h * 0.8), QPointF(x + w * 0.72, y + h * 0.8))


def _itrend(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    path = QPainterPath()
    path.moveTo(x + w * 0.1, y + h * 0.82)
    path.lineTo(x + w * 0.34, y + h * 0.6)
    path.lineTo(x + w * 0.58, y + h * 0.66)
    path.lineTo(x + w * 0.86, y + h * 0.24)
    p.drawPath(path)
    p.drawLine(QPointF(x + w * 0.86, y + h * 0.24), QPointF(x + w * 0.7, y + h * 0.2))
    p.drawLine(QPointF(x + w * 0.86, y + h * 0.24), QPointF(x + w * 0.8, y + h * 0.38))


def _ichat(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    p.drawRoundedRect(QRectF(x, y + h * 0.12, w, h * 0.62), w * 0.1, w * 0.1)
    p.drawLine(QPointF(x + w * 0.26, y + h * 0.74), QPointF(x + w * 0.18, y + h * 0.9))
    p.drawLine(QPointF(x + w * 0.27, y + h * 0.42), QPointF(x + w * 0.27, y + h * 0.42))
    p.drawLine(QPointF(x + w * 0.5, y + h * 0.42), QPointF(x + w * 0.5, y + h * 0.42))
    p.drawLine(QPointF(x + w * 0.73, y + h * 0.42), QPointF(x + w * 0.73, y + h * 0.42))


def _ibell(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx = x + w / 2
    body = QPainterPath()
    body.moveTo(cx, y + h * 0.1)
    body.cubicTo(cx - w * 0.24, y + h * 0.1, cx - w * 0.24, y + h * 0.4, cx - w * 0.22, y + h * 0.52)
    body.lineTo(cx - w * 0.3, y + h * 0.7)
    body.lineTo(cx + w * 0.3, y + h * 0.7)
    body.lineTo(cx + w * 0.22, y + h * 0.52)
    body.cubicTo(cx + w * 0.24, y + h * 0.4, cx + w * 0.24, y + h * 0.1, cx, y + h * 0.1)
    p.drawPath(body)
    p.drawLine(QPointF(cx, y + h * 0.7), QPointF(cx, y + h * 0.78))
    p.drawLine(QPointF(cx - w * 0.12, y + h * 0.84), QPointF(cx + w * 0.12, y + h * 0.84))


def _igear(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx, cy = x + w / 2, y + h / 2
    for i in range(8):
        p.save()
        p.translate(cx, cy)
        p.rotate(i * 45)
        p.drawLine(QPointF(0, -w * 0.2), QPointF(0, -w * 0.3))
        p.restore()
    p.drawEllipse(QPointF(cx, cy), w * 0.2, h * 0.2)
    p.drawLine(QPointF(cx, cy), QPointF(cx, cy))


def _ifile(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    p.drawRoundedRect(QRectF(x + w * 0.14, y + h * 0.06, w * 0.72, h * 0.88), w * 0.06, w * 0.06)
    p.drawLine(QPointF(x + w * 0.3, y + h * 0.3), QPointF(x + w * 0.7, y + h * 0.3))
    p.drawLine(QPointF(x + w * 0.3, y + h * 0.5), QPointF(x + w * 0.6, y + h * 0.5))
    p.drawLine(QPointF(x + w * 0.3, y + h * 0.7), QPointF(x + w * 0.7, y + h * 0.7))


def _idownload(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx = x + w / 2
    p.drawLine(QPointF(cx, y + h * 0.1), QPointF(cx, y + h * 0.58))
    p.drawLine(QPointF(cx - w * 0.14, y + h * 0.46), QPointF(cx, y + h * 0.58))
    p.drawLine(QPointF(cx + w * 0.14, y + h * 0.46), QPointF(cx, y + h * 0.58))
    p.drawLine(QPointF(x + w * 0.1, y + h * 0.78), QPointF(x + w * 0.9, y + h * 0.78))
    p.drawLine(QPointF(x + w * 0.1, y + h * 0.78), QPointF(x + w * 0.16, y + h * 0.9))
    p.drawLine(QPointF(x + w * 0.9, y + h * 0.78), QPointF(x + w * 0.84, y + h * 0.9))
    p.drawLine(QPointF(x + w * 0.16, y + h * 0.9), QPointF(x + w * 0.84, y + h * 0.9))


def _ireply(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    path = QPainterPath()
    path.moveTo(x + w * 0.12, y + h * 0.86)
    path.lineTo(x + w * 0.78, y + h * 0.86)
    path.lineTo(x + w * 0.78, y + h * 0.3)
    p.drawPath(path)
    p.drawLine(QPointF(x + w * 0.78, y + h * 0.3), QPointF(x + w * 0.56, y + h * 0.14))
    p.drawLine(QPointF(x + w * 0.78, y + h * 0.3), QPointF(x + w * 0.56, y + h * 0.46))


def _iup(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx = x + w / 2
    p.drawLine(QPointF(cx, y + h * 0.9), QPointF(cx, y + h * 0.16))
    p.drawLine(QPointF(cx - w * 0.14, y + h * 0.32), QPointF(cx, y + h * 0.16))
    p.drawLine(QPointF(cx + w * 0.14, y + h * 0.32), QPointF(cx, y + h * 0.16))


def _idown(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx = x + w / 2
    p.drawLine(QPointF(cx, y + h * 0.1), QPointF(cx, y + h * 0.84))
    p.drawLine(QPointF(cx - w * 0.14, y + h * 0.68), QPointF(cx, y + h * 0.84))
    p.drawLine(QPointF(cx + w * 0.14, y + h * 0.68), QPointF(cx, y + h * 0.84))


def _iwarning(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx = x + w / 2
    tri = QPainterPath()
    tri.moveTo(cx, y + h * 0.08)
    tri.lineTo(x + w * 0.94, y + h * 0.86)
    tri.lineTo(x + w * 0.06, y + h * 0.86)
    tri.closeSubpath()
    p.drawPath(tri)
    p.drawLine(QPointF(cx, y + h * 0.32), QPointF(cx, y + h * 0.56))
    p.drawLine(QPointF(cx, y + h * 0.7), QPointF(cx, y + h * 0.7))


def _iinfo(p: QPainter, r: QRectF) -> None:
    c = r.center()
    p.drawEllipse(c, r.width() / 2, r.height() / 2)
    p.drawLine(QPointF(c.x(), c.y() - r.height() * 0.2), QPointF(c.x(), c.y() - r.height() * 0.2))
    p.drawLine(QPointF(c.x(), c.y() + r.height() * 0.06), QPointF(c.x(), c.y() + r.height() * 0.32))


def _iflag(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    p.drawLine(QPointF(x + w * 0.3, y + h * 0.12), QPointF(x + w * 0.3, y + h * 0.9))
    path = QPainterPath()
    path.moveTo(x + w * 0.3, y + h * 0.12)
    path.lineTo(x + w * 0.84, y + h * 0.3)
    path.lineTo(x + w * 0.3, y + h * 0.46)
    p.drawPath(path)


def _imedal(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx = x + w / 2
    p.drawEllipse(QPointF(cx, y + h * 0.52), w * 0.24, h * 0.24)
    p.drawLine(QPointF(cx, y + h * 0.28), QPointF(x + w * 0.3, y + h * 0.84))
    p.drawLine(QPointF(cx, y + h * 0.28), QPointF(x + w * 0.7, y + h * 0.84))


def _igem(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx = x + w / 2
    path = QPainterPath()
    path.moveTo(cx, y + h * 0.1)
    path.lineTo(x + w * 0.86, y + h * 0.4)
    path.lineTo(x + w * 0.58, y + h * 0.88)
    path.lineTo(x + w * 0.42, y + h * 0.88)
    path.lineTo(x + w * 0.14, y + h * 0.4)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(x + w * 0.14, y + h * 0.4), QPointF(x + w * 0.86, y + h * 0.4))
    p.drawLine(QPointF(x + w * 0.38, y + h * 0.4), QPointF(cx, y + h * 0.88))
    p.drawLine(QPointF(x + w * 0.62, y + h * 0.4), QPointF(cx, y + h * 0.88))


def _icrown(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx = x + w / 2
    path = QPainterPath()
    path.moveTo(x + w * 0.1, y + h * 0.62)
    path.lineTo(x + w * 0.1, y + h * 0.48)
    path.lineTo(x + w * 0.3, y + h * 0.16)
    path.lineTo(cx, y + h * 0.42)
    path.lineTo(x + w * 0.7, y + h * 0.16)
    path.lineTo(x + w * 0.9, y + h * 0.48)
    path.lineTo(x + w * 0.9, y + h * 0.62)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(x + w * 0.1, y + h * 0.62), QPointF(x + w * 0.9, y + h * 0.62))
    p.drawLine(QPointF(x + w * 0.1, y + h * 0.5), QPointF(x + w * 0.1, y + h * 0.5))
    p.drawLine(QPointF(cx, y + h * 0.42), QPointF(cx, y + h * 0.42))
    p.drawLine(QPointF(x + w * 0.9, y + h * 0.5), QPointF(x + w * 0.9, y + h * 0.5))


def _irocket(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx = x + w / 2
    body = QPainterPath()
    body.moveTo(cx, y + h * 0.06)
    body.lineTo(cx + w * 0.2, y + h * 0.36)
    body.lineTo(cx + w * 0.2, y + h * 0.6)
    body.lineTo(cx - w * 0.2, y + h * 0.6)
    body.lineTo(cx - w * 0.2, y + h * 0.36)
    body.closeSubpath()
    p.drawPath(body)
    p.drawEllipse(QPointF(cx, y + h * 0.42), w * 0.08, h * 0.08)
    left = QPainterPath()
    left.moveTo(cx - w * 0.2, y + h * 0.5)
    left.lineTo(x + w * 0.14, y + h * 0.86)
    left.lineTo(x + w * 0.16, y + h * 0.6)
    p.drawPath(left)
    right = QPainterPath()
    right.moveTo(cx + w * 0.2, y + h * 0.5)
    right.lineTo(x + w * 0.86, y + h * 0.86)
    right.lineTo(x + w * 0.84, y + h * 0.6)
    p.drawPath(right)
    p.drawLine(QPointF(cx - w * 0.08, y + h * 0.6), QPointF(cx, y + h * 0.9))
    p.drawLine(QPointF(cx + w * 0.08, y + h * 0.6), QPointF(cx, y + h * 0.9))


def _iflame(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx = x + w / 2
    path = QPainterPath()
    path.moveTo(cx, y + h * 0.04)
    path.cubicTo(cx + w * 0.3, y + h * 0.36, cx + w * 0.22, y + h * 0.7, cx, y + h * 0.92)
    path.cubicTo(cx - w * 0.22, y + h * 0.7, cx - w * 0.3, y + h * 0.36, cx, y + h * 0.04)
    p.drawPath(path)
    inner = QPainterPath()
    inner.moveTo(cx, y + h * 0.44)
    inner.cubicTo(cx + w * 0.1, y + h * 0.62, cx + w * 0.06, y + h * 0.8, cx, y + h * 0.9)
    p.drawPath(inner)


def _istar(p: QPainter, r: QRectF) -> None:
    cx, cy = r.center().x(), r.center().y()
    w, h = r.width(), r.height()
    path = QPainterPath()
    for i in range(10):
        angle = -90 + i * 36
        rad = (w * 0.45 if i % 2 == 0 else w * 0.18)
        px = cx + rad * math.cos(math.radians(angle))
        py = cy + rad * math.sin(math.radians(angle))
        if i == 0:
            path.moveTo(px, py)
        else:
            path.lineTo(px, py)
    path.closeSubpath()
    p.drawPath(path)


def _ibolt(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx = x + w / 2
    path = QPainterPath()
    path.moveTo(cx + w * 0.18, y + h * 0.08)
    path.lineTo(cx - w * 0.2, y + h * 0.54)
    path.lineTo(cx - w * 0.02, y + h * 0.54)
    path.lineTo(cx - w * 0.18, y + h * 0.92)
    path.lineTo(cx + w * 0.2, y + h * 0.44)
    path.lineTo(cx + w * 0.02, y + h * 0.44)
    path.closeSubpath()
    p.drawPath(path)


def _ilock(p: QPainter, r: QRectF) -> None:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx = x + w / 2
    p.drawArc(QRectF(cx - w * 0.2, y + h * 0.08, w * 0.4, h * 0.5), 180 * 16, 180 * 16)
    p.drawRoundedRect(QRectF(x + w * 0.16, y + h * 0.44, w * 0.68, h * 0.46), w * 0.05, w * 0.05)
    p.drawLine(QPointF(cx, y + h * 0.62), QPointF(cx, y + h * 0.62))


_ICON_DRAW: Dict[str, Callable[[QPainter, QRectF], None]] = {
    "dot": _idot,
    "home": _ihome,
    "package": _ipackage,
    "chart": _ichart,
    "scale": _iscale,
    "bulb": _ibulb,
    "trophy": _itrophy,
    "trend": _itrend,
    "chat": _ichat,
    "bell": _ibell,
    "gear": _igear,
    "file": _ifile,
    "download": _idownload,
    "reply": _ireply,
    "trend-up": _iup,
    "trend-down": _idown,
    "warning": _iwarning,
    "info": _iinfo,
    "flag": _iflag,
    "medal": _imedal,
    "gem": _igem,
    "crown": _icrown,
    "rocket": _irocket,
    "flame": _iflame,
    "star": _istar,
    "bolt": _ibolt,
    "lock": _ilock,
}

INSIGHT_ICONS = {"positive": "trend-up", "negative": "warning", "info": "info"}
INSIGHT_COLORS = {"positive": SUCCESS, "negative": ERROR, "info": ACCENT}
