"""Reusable widgets: stat cards, pyqtgraph chart cards, activity feed, mod/badge/insight cards."""

from __future__ import annotations

import datetime
import time
from typing import Any, Dict, List, Optional

import pyqtgraph as pg
from PyQt6.QtCore import QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.icons import _apply_shadow, _icon, _icon_label
from ui.theme import (
    ACCENT,
    ACCENT_DARK,
    BORDER,
    CARD,
    ERROR,
    FAINT,
    GRAY,
    PANEL,
    PANEL2,
    SUCCESS,
    TEXT,
    WARNING,
)


def relative_time(iso_str: Any) -> str:
    """Human-friendly time like '2h ago', 'just now'."""
    try:
        now = datetime.datetime.now().astimezone()
        ts = datetime.datetime.fromisoformat(str(iso_str))
        if ts.tzinfo is None:
            ts = ts.astimezone()
        diff = now - ts
        secs = int(diff.total_seconds())
        if secs < 60:
            return "just now"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        if secs < 86400 * 7:
            return f"{secs // 86400}d ago"
        return ts.strftime("%b %d, %Y")
    except Exception:  # noqa: BLE001
        return str(iso_str)[:16]


def format_num(value: Any) -> str:
    try:
        return f"{int(value or 0):,}"
    except Exception:  # noqa: BLE001
        return str(value or "—")


class FlowLayout(QLayout):
    """Responsive grid: cards wrap into columns that fit the available width."""

    def __init__(self, parent: Optional[QWidget] = None, spacing: int = 12, min_width: int = 300) -> None:
        super().__init__(parent)
        self.setSpacing(spacing)
        self.setContentsMargins(0, 0, 0, 0)
        self._items: List[QLayoutItem] = []
        self._min_width = min_width
        self._spacing = spacing

    def addItem(self, item) -> None:  # noqa: D102
        self._items.append(item)

    def count(self) -> int:  # noqa: D102
        return len(self._items)

    def itemAt(self, index: int):  # noqa: D102
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):  # noqa: D102
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):  # noqa: D102
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: D102
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: D102
        return self._measure(width)

    def minimumHeightForWidth(self, width: int) -> int:  # noqa: D102
        return self._measure(width)

    def sizeHint(self) -> QSize:  # noqa: D102
        return QSize(self._min_width, self._measure(self._min_width))

    def minimumSize(self) -> QSize:  # noqa: D102
        return QSize(self._min_width, 0)

    def add_card(self, widget: QWidget) -> None:
        self.addWidget(widget)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def clear(self) -> None:
        while self._items:
            item = self.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _columns_for(self, width: int) -> int:
        if width < self._min_width:
            return 1
        return max(1, width // self._min_width)

    def _measure(self, width: int) -> int:
        if not self._items:
            return 0
        heights = [it.sizeHint().height() for it in self._items if it.widget()]
        if not heights:
            return 0
        h = max(heights)
        cols = self._columns_for(width)
        rows = (len(heights) + cols - 1) // cols
        return rows * h + (rows - 1) * self._spacing

    def setGeometry(self, rect) -> None:  # noqa: N802
        super().setGeometry(rect)
        if not self._items:
            return
        items = [it for it in self._items if it.widget()]
        width = rect.width()
        cols = self._columns_for(width)
        item_w = (width - (cols - 1) * self._spacing) // cols
        for i, it in enumerate(items):
            col = i % cols
            row = i // cols
            x = rect.x() + col * (item_w + self._spacing)
            y = rect.y() + row * (it.sizeHint().height() + self._spacing)
            it.setGeometry(QRect(x, y, item_w, it.sizeHint().height()))


# --------------------------------------------------------------------------
# background worker
# --------------------------------------------------------------------------


def panel(parent: QWidget) -> QFrame:
    frame = QFrame(parent)
    frame.setObjectName("Panel")
    return frame


def section_label(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("SectionTitle")
    return label


def make_table(headers: List[str], selectable: bool = True) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setWordWrap(False)
    if selectable:
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    else:
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    header = table.horizontalHeader()
    header.setStretchLastSection(True)
    header.setHighlightSections(False)
    table.setSortingEnabled(False)
    return table


def fill_table(table: QTableWidget, rows: List[List[Any]]) -> None:
    table.setSortingEnabled(False)
    table.setRowCount(0)
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            item = QTableWidgetItem("" if value is None else str(value))
            if c == 0:
                item.setData(Qt.ItemDataRole.UserRole, value)
            table.setItem(r, c, item)
    table.resizeColumnsToContents()


class StatCard(QFrame):
    """Dashboard stat card with count-up animation and colored delta."""

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setMinimumHeight(98)

        self._title = QLabel(str(title).upper())
        self._title.setObjectName("StatCaption")
        self._value = QLabel("—")
        self._value.setObjectName("StatValue")
        self._delta = QLabel("")
        self._delta.setObjectName("StatDelta")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 13, 16, 13)
        lay.setSpacing(2)
        lay.addWidget(self._title)
        lay.addWidget(self._value)
        lay.addWidget(self._delta)

        self._current = 0
        self._target = 0
        self._start = 0
        self._t0 = 0.0
        self._dur = 0.6
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._step)
        _apply_shadow(self)

    def set_value(self, target: Any, delta_text: str = "", delta_color: Optional[str] = None) -> None:
        try:
            target = int(float(target))
        except Exception:  # noqa: BLE001
            target = 0
        self._delta.setText(delta_text)
        self._delta.setStyleSheet(f"color: {delta_color or GRAY}; font-size: 12px;")
        self._target = target
        self._start = self._current
        self._t0 = time.monotonic()
        self._timer.start()

    def set_text(self, text: str, delta_text: str = "", delta_color: Optional[str] = None) -> None:
        self._timer.stop()
        self._value.setText(str(text))
        self._delta.setText(delta_text)
        self._delta.setStyleSheet(f"color: {delta_color or GRAY}; font-size: 12px;")

    def _step(self) -> None:
        frac = min(1.0, (time.monotonic() - self._t0) / self._dur)
        eased = 1 - (1 - frac) ** 3
        val = int(round(self._start + (self._target - self._start) * eased))
        self._value.setText(f"{val:,}")
        if frac >= 1.0:
            self._timer.stop()
            self._current = self._target


def _date_to_ts(d: datetime.date) -> float:
    return datetime.datetime.combine(d, datetime.time()).timestamp()


class _PlainBar(pg.BarGraphItem):
    """BarGraphItem that does not register as a plot-data curve.

    pyqtgraph 0.14's ``PlotItem`` treats anything where
    ``implements('plotData')`` is true as a curve and calls
    ``setDownsampling``/``setFftMode`` on it during ``updateDownsampling``
    /``updateSpectrumMode``; ``BarGraphItem`` lacks those methods, which
    crashes with an AttributeError. Reporting no interface keeps bars
    rendering exactly the same while excluding them from curve management.
    """

    def implements(self, interface: str) -> bool:  # noqa: D102
        return False


class PlotCard(QFrame):
    """Panel with an interactive pyqtgraph chart and a hover readout line."""

    def __init__(self, title: str, subtitle: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self._series: List[Dict[str, Any]] = []

        head = QLabel(title)
        head.setObjectName("SectionTitle")
        sub = QLabel(subtitle)
        sub.setObjectName("Caption")

        self.plot = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem()})
        self.plot.setBackground(CARD)
        self.plot.setMinimumHeight(230)
        pi = self.plot.getPlotItem()
        pi.showGrid(x=True, y=True, alpha=0.18)
        pi.setMouseEnabled(x=True, y=False)
        for axis_name in ("left", "bottom"):
            axis = pi.getAxis(axis_name)
            axis.setPen(pg.mkPen(BORDER))
            axis.setTextPen(pg.mkPen(FAINT))
            try:
                axis.setTickFont(QFont("Segoe UI", 9))
            except Exception:  # noqa: BLE001
                pass

        self.info = QLabel("Hover for values  \u00b7  drag to zoom")
        self.info.setObjectName("Caption")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 10)
        lay.setSpacing(8)
        lay.addWidget(head)
        lay.addWidget(sub)
        lay.addWidget(self.plot, 1)
        lay.addWidget(self.info)

        self.plot.scene().sigMouseMoved.connect(self._on_hover)

    # ---- drawing helpers ------------------------------------------------
    def clear_chart(self) -> None:
        self.plot.clear()
        self._series = []

    def set_ylabel(self, text: str) -> None:
        self.plot.getPlotItem().setLabel("left", text)

    def add_bars(self, dates, values, color: str, name: str = "", alpha: int = 255) -> None:
        ts = [_date_to_ts(d) for d in dates]
        brush = QColor(color)
        brush.setAlpha(alpha)
        item = _PlainBar(
            x=ts, height=values, width=86400 * 0.68,
            brush=pg.mkBrush(brush), pen=pg.mkPen(color),
        )
        self.plot.addItem(item)
        self._series.append({"times": ts, "values": list(values), "labels": list(dates), "name": name})

    def add_line(self, dates, values, color: str, width: int = 2, fill: bool = False, name: str = "") -> None:
        ts = [_date_to_ts(d) for d in dates]
        item = self.plot.plot(
            ts, values, pen=pg.mkPen(color, width=width), antialias=True,
        )
        if fill:
            item.setFillLevel(0)
            brush = QColor(color)
            brush.setAlpha(45)
            item.setBrush(pg.mkBrush(brush))
        self._series.append({"times": ts, "values": list(values), "labels": list(dates), "name": name})

    def add_milestone(self, date: datetime.date, threshold: int) -> None:
        ts = _date_to_ts(date)
        self.plot.addItem(pg.InfiniteLine(
            pos=ts, angle=90, pen=pg.mkPen(WARNING, width=1, style=Qt.PenStyle.DashLine),
        ))
        text = pg.TextItem(f"{threshold:,}", color=WARNING, anchor=(1, 1))
        text.setPos(ts, threshold)
        self.plot.addItem(text)

    def _on_hover(self, pos) -> None:
        vb = self.plot.getPlotItem().getViewBox()
        if not vb.sceneBoundingRect().contains(pos):
            return
        mouse = vb.mapSceneToView(pos)
        x = mouse.x()
        best = None
        best_dist = None
        for entry in self._series:
            times = entry["times"]
            if not times:
                continue
            idx = min(range(len(times)), key=lambda i: abs(times[i] - x))
            dist = abs(times[idx] - x)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best = (entry, idx)
        if best is None:
            self.info.setText("")
            return
        entry, idx = best
        label = entry["labels"][idx]
        if isinstance(label, datetime.date):
            label = label.strftime("%Y-%m-%d")
        prefix = f"{entry['name']}   " if entry.get("name") else ""
        self.info.setText(f"{prefix}{label}   \u2192   {entry['values'][idx]:,}")


class InsightCard(QFrame):
    """Single insight line with a sentiment-colored accent bar."""

    KIND_ICON = {"positive": "trend-up", "negative": "warning", "info": "info"}
    KIND_COLOR = {"positive": SUCCESS, "negative": ERROR, "info": ACCENT}

    def __init__(self, insight: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        kind = insight.get("kind", "info")
        color = self.KIND_COLOR.get(kind, ACCENT)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(12)

        bar = QFrame()
        bar.setFixedWidth(4)
        bar.setStyleSheet(f"background: {color}; border: none; border-radius: 2px;")
        lay.addWidget(bar)

        icon = _icon_label(self.KIND_ICON.get(kind, "info"), color, 20)
        lay.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

        col = QVBoxLayout()
        col.setSpacing(2)
        head = QHBoxLayout()
        title = QLabel(insight.get("title", ""))
        title.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {color}; border: none; background: transparent;")
        head.addWidget(title)
        head.addStretch(1)
        if insight.get("mod"):
            mod = QLabel(insight["mod"])
            mod.setStyleSheet(f"color: {GRAY}; font-size: 11px; border: none; background: transparent;")
            head.addWidget(mod)
        col.addLayout(head)
        detail = QLabel(insight.get("detail", ""))
        detail.setWordWrap(True)
        detail.setStyleSheet("font-size: 12px; color: #334155; border: none; background: transparent;")
        col.addWidget(detail)
        lay.addLayout(col, 1)


class BadgeCard(QFrame):
    """Single achievement badge, highlighted when unlocked."""

    ICONS = {
        "tracked": "star",
        "milestone-100000": "flag",
        "milestone-250000": "medal",
        "milestone-500000": "medal",
        "milestone-1000000": "medal",
        "milestone-2500000": "gem",
        "milestone-5000000": "crown",
        "milestone-10000000": "rocket",
        "best-week": "trophy",
        "steady": "trend",
        "big-day": "flame",
        "community": "chat",
        "fast-riser": "bolt",
    }

    def __init__(self, badge: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("BadgeCard")
        unlocked = bool(badge.get("unlocked"))
        self.setStyleSheet(
            f"QFrame#BadgeCard {{ border: 1px solid {ACCENT}; }}" if unlocked
            else f"QFrame#BadgeCard {{ border: 1px solid {BORDER}; }}"
        )
        icon_key = self.ICONS.get(badge.get("key", ""), "star") if unlocked else "lock"
        border_color = ACCENT if unlocked else FAINT
        text_color = TEXT if unlocked else FAINT

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(4)
        top = QHBoxLayout()
        ic = _icon_label(icon_key, border_color, 26)
        top.addWidget(ic)
        top.addStretch(1)
        if unlocked and badge.get("date"):
            d = QLabel(str(badge["date"]))
            d.setStyleSheet(f"color: {GRAY}; font-size: 10px; background: transparent; border: none;")
            top.addWidget(d)
        lay.addLayout(top)
        title = QLabel(badge.get("title", ""))
        title.setWordWrap(True)
        title.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {text_color}; background: transparent; border: none;")
        lay.addWidget(title)
        detail = QLabel(badge.get("detail", ""))
        detail.setWordWrap(True)
        detail.setStyleSheet(f"color: {GRAY}; font-size: 11px; background: transparent; border: none;")
        lay.addWidget(detail)
        _apply_shadow(self, 18, 2)


class ActivityFeed(QFrame):
    """Sidebar panel listing recent download / comment events."""

    KIND_STYLE = {
        "download": ("download", SUCCESS),
        "comment": ("chat", ACCENT),
        "reply": ("reply", WARNING),
    }

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        header = QLabel("ACTIVITY")
        header.setObjectName("SectionTitle")
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._list_lay = QVBoxLayout(self._container)
        self._list_lay.setContentsMargins(2, 2, 2, 2)
        self._list_lay.setSpacing(2)
        self._list_lay.addStretch(1)
        self._scroll.setWidget(self._container)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 12)
        lay.setSpacing(10)
        lay.addWidget(header)
        lay.addWidget(self._scroll)
        self._empty = None

    def refresh(self, storage: Storage) -> None:
        while self._list_lay.count() > 1:
            item = self._list_lay.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if self._empty:
            self._empty.deleteLater()
            self._empty = None

        rows = storage.recent_events(40)
        if not rows:
            self._empty = QLabel("No activity yet.\n\nRun a poll to start\nrecording events.")
            self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._empty.setObjectName("Hint")
            self._empty.setStyleSheet(f"color: {FAINT}; padding: 24px;")
            self._list_lay.insertWidget(0, self._empty)
            return

        for event in rows:
            kind = event["kind"] or "download"
            icon_name, color = self.KIND_STYLE.get(kind, ("dot", GRAY))
            row = QFrame()
            row.setObjectName("EventRow")
            h = QHBoxLayout(row)
            h.setContentsMargins(8, 6, 8, 6)
            h.setSpacing(8)

            icon_label = _icon_label(icon_name, color, 16)
            icon_label.setFixedWidth(20)

            body = QVBoxLayout()
            body.setSpacing(1)
            head = QLabel(str(event["mod_name"] or "ModDB"))
            head.setStyleSheet(f"color: {color}; font-weight: 700; font-size: 12px; background: transparent;")
            msg = QLabel(str(event["message"]))
            msg.setWordWrap(True)
            msg.setStyleSheet(f"color: {GRAY}; font-size: 12px; background: transparent;")
            body.addWidget(head)
            body.addWidget(msg)

            stamp = QLabel(relative_time(event["created_at"]))
            stamp.setStyleSheet(f"color: {FAINT}; font-size: 11px; background: transparent;")
            stamp.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

            h.addWidget(icon_label)
            h.addLayout(body, 1)
            h.addWidget(stamp)
            self._list_lay.insertWidget(self._list_lay.count() - 1, row)


class ModCard(QFrame):
    """Compact card for a single tracked mod on the My Mods page."""

    open_requested = pyqtSignal(str)
    refresh_requested = pyqtSignal(int)
    favorite_toggled = pyqtSignal(str, bool)
    remove_requested = pyqtSignal(str)
    export_requested = pyqtSignal()

    TYPE_BADGE = {
        "mod": ("MOD", ACCENT),
        "addon": ("ADDON", SUCCESS),
        "file": ("FILE", WARNING),
    }

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ModCard")
        self.setFixedHeight(148)
        self._url = ""
        self._name_id = ""
        self._mod_id = 0
        self._favorite = False

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)

        # header: badge + name + favorite star
        self._badge = QLabel("MOD")
        self._badge.setFixedSize(54, 20)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setStyleSheet(
            "font-size: 9px; font-weight: 800; letter-spacing: 1px; border-radius: 4px;"
        )
        self._name = QLabel()
        self._name.setStyleSheet("font-size: 14px; font-weight: 700;")
        self._name.setToolTip("")
        self._full_name = ""
        self._star = QToolButton()
        self._star.setFixedSize(26, 26)
        self._star.setCursor(Qt.CursorShape.PointingHandCursor)
        self._star.setToolTip("Toggle favorite")
        self._star.clicked.connect(self._toggle_favorite)
        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(self._badge)
        header.addWidget(self._name, 1)
        header.addWidget(self._star)
        lay.addLayout(header)

        # numbers
        self._dl = QLabel("—")
        self._dl.setObjectName("StatValue")
        self._dl.setStyleSheet("font-size: 20px;")
        self._dl_cap = QLabel("DOWNLOADS")
        self._dl_cap.setObjectName("StatCaption")
        num_col = QVBoxLayout()
        num_col.setSpacing(0)
        num_col.addWidget(self._dl)
        num_col.addWidget(self._dl_cap)
        self._growth = QLabel("")
        self._growth.setStyleSheet(f"color: {SUCCESS}; font-size: 12px; font-weight: 600;")
        self._meta = QLabel("")
        self._meta.setStyleSheet(f"color: {GRAY}; font-size: 12px;")
        right_col = QVBoxLayout()
        right_col.setSpacing(3)
        right_col.addStretch(1)
        right_col.addWidget(self._growth)
        right_col.addWidget(self._meta)
        numbers = QHBoxLayout()
        numbers.setSpacing(20)
        numbers.addLayout(num_col)
        numbers.addLayout(right_col, 1)
        lay.addLayout(numbers)

        # footer: updated stamp + actions
        self._stamp = QLabel("")
        self._stamp.setStyleSheet(f"color: {FAINT}; font-size: 11px;")
        self._open_btn = QPushButton("Open")
        self._open_btn.clicked.connect(lambda: self.open_requested.emit(self._url))
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(lambda: self.refresh_requested.emit(self._mod_id))
        footer = QHBoxLayout()
        footer.setSpacing(8)
        footer.addWidget(self._stamp)
        footer.addStretch(1)
        footer.addWidget(self._open_btn)
        footer.addWidget(self._refresh_btn)
        lay.addLayout(footer)
        _apply_shadow(self)

    # ---- data -----------------------------------------------------------
    def set_data(self, totals: Dict[str, Any], meta: Dict[str, Any],
                 delta_7d: int = 0, updated: str = "") -> None:
        self._mod_id = int(totals["id"])
        self._name_id = str(totals.get("name_id") or meta.get("name_id") or "")
        self._url = str(totals.get("url") or meta.get("url") or "")
        self._favorite = bool(totals.get("favorite", meta.get("favorite", False)))
        content_type = str(meta.get("content_type") or totals.get("content_type") or "mod")
        name = str(totals.get("name") or meta.get("name") or self._name_id)

        badge_text, badge_color = self.TYPE_BADGE.get(content_type, ("MOD", ACCENT))
        self._badge.setText(badge_text)
        self._badge.setStyleSheet(
            "font-size: 9px; font-weight: 800; letter-spacing: 1px; border-radius: 4px;"
            f" background: {badge_color}22; color: {badge_color}; border: 1px solid {badge_color}55;"
        )
        self._name.setText(name)
        self._full_name = name
        self._name.setToolTip(name)
        self._refresh_name_elide()

        self._dl.setText(format_num(totals.get("downloads_total")))
        self._dl_cap.setText(f"DOWNLOADS · +{format_num(totals.get('downloads_today'))} TODAY")
        if delta_7d > 0:
            self._growth.setText(f"▲ +{delta_7d:,} last 7 days")
            self._growth.setStyleSheet(f"color: {SUCCESS}; font-size: 12px; font-weight: 600;")
        else:
            self._growth.setText("— no change this week")
            self._growth.setStyleSheet(f"color: {GRAY}; font-size: 12px;")
        rank = totals.get("rank")
        parts = []
        if rank is not None:
            parts.append(f"Rank {rank}{'/' + str(totals['rank_total']) if totals.get('rank_total') else ''}")
        parts.append(f"Watchers {format_num(totals.get('watchers'))}")
        parts.append(f"Visits {format_num(totals.get('visits'))}")
        parts.append(f"Comments {totals.get('comments', 0)}")
        parts.append(f"Replies {totals.get('replies', 0)}")
        self._meta.setText(" · ".join(parts))
        self._stamp.setText(f"Updated {relative_time(updated)}" if updated else "")

        star = "★" if self._favorite else "☆"
        self._star.setText(star)
        color = WARNING if self._favorite else FAINT
        hover = f" QToolButton:hover {{ color: {WARNING}; }}" if not self._favorite else ""
        self._star.setStyleSheet(
            "QToolButton { border: none; background: transparent; font-size: 20px;"
            f" color: {color}; }}" + hover
        )

    def matches(self, text: str) -> bool:
        needle = text.strip().lower()
        if not needle:
            return True
        hay = f"{self._name.text()} {self._name_id} {self._url}".lower()
        return needle in hay

    # ---- actions --------------------------------------------------------
    def _refresh_name_elide(self) -> None:
        if not self._full_name:
            return
        fm = self._name.fontMetrics()
        available = max(60, self._name.width())
        self._name.setText(fm.elidedText(self._full_name, Qt.TextElideMode.ElideRight, available))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh_name_elide()

    def _toggle_favorite(self) -> None:
        self._favorite = not self._favorite
        self._star.setText("★" if self._favorite else "☆")
        self._star.setStyleSheet(
            "QToolButton { border: none; background: transparent; font-size: 20px;"
            f" color: {WARNING if self._favorite else FAINT}; }}"
        )
        self.favorite_toggled.emit(self._name_id, self._favorite)

    def _show_menu(self, pos) -> None:
        menu = QMenu(self)
        fav_action = menu.addAction("Unfavorite" if self._favorite else "Favorite")
        menu.addSeparator()
        menu.addAction("Refresh mod...")
        open_action = menu.addAction("Open on ModDB")
        copy_action = menu.addAction("Copy URL")
        menu.addSeparator()
        export_action = menu.addAction("Export JSON...")
        remove_action = menu.addAction("Remove from tracking")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == fav_action:
            self._toggle_favorite()
        elif chosen == open_action:
            self.open_requested.emit(self._url)
        elif chosen == copy_action:
            QApplication.clipboard().setText(self._url)
        elif chosen == export_action:
            self.export_requested.emit()
        elif chosen == remove_action:
            self.remove_requested.emit(self._name_id)


# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------
