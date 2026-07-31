"""PyQt6 GUI for the ModDB Tracker.

Shows charts, mod stats, download history, comments, events and lets you
run polls / rescans from the UI. Data tables live in the same SQLite DB the
CLI uses, so the GUI and the scheduled task are interchangeable.

Run with:  python gui.py [--config path/to/config.json]
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import QObject, QRect, QSize, QThread, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QDesktopServices, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLayoutItem,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import transport
from storage import Storage

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tracker  # noqa: E402
from tracker import (  # noqa: E402  (imports depend on sys.path above)
    CONFIG_FILE,
    discover_mods,
    load_config,
    run_poll,
    save_config,
)

logger = logging.getLogger("tracker.gui")

VERSION = "2.0.0"

# --------------------------------------------------------------------------
# palette (dark blue theme)
# --------------------------------------------------------------------------

BG = "#0F172A"
CARD = "#1E293B"
PANEL = "#1E293B"
PANEL2 = "#243247"
SURFACE = "#273449"
BORDER = "#334155"
TEXT = "#E2E8F0"
GRAY = "#94A3B8"
FAINT = "#64748B"
ACCENT = "#3B82F6"
ACCENT_DARK = "#2563EB"
SUCCESS = "#22C55E"
WARNING = "#F59E0B"
ERROR = "#EF4444"


# --------------------------------------------------------------------------
# tray icon
# --------------------------------------------------------------------------

def tray_icon_path() -> str:
    """Return a cached .png for the tray icon, drawing it if missing."""
    path = Path(__file__).resolve().parent / "tray_icon.png"
    if path.exists():
        return str(path)
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(ACCENT))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 14, 14)
    painter.setPen(QColor("#FFFFFF"))
    font = QFont("Segoe UI", 22, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "M")
    painter.end()
    pixmap.save(str(path))
    return str(path)


# --------------------------------------------------------------------------
# global stylesheet
# --------------------------------------------------------------------------

QSS = f"""
* {{
    outline: none;
}}
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "Segoe UI";
    font-size: 13px;
}}
QLabel {{ background: transparent; }}

QFrame#Panel, QFrame#PanelSecondary {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QFrame#TopBar {{
    background-color: {BG};
    border-bottom: 1px solid {BORDER};
    border-radius: 0px;
}}
QFrame#StatCard, QFrame#ModCard {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#ModCard:hover {{
    border: 1px solid {ACCENT};
    background-color: {SURFACE};
}}
QFrame#EventRow {{
    background-color: transparent;
    border: none;
}}
QFrame#EventRow:hover {{ background-color: {PANEL2}; border-radius: 6px; }}

QPushButton {{
    background-color: {PANEL2};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 7px 14px;
    font-weight: 600;
}}
QPushButton:hover {{ border-color: {ACCENT}; background-color: {SURFACE}; }}
QPushButton:pressed {{ background-color: {BORDER}; }}
QPushButton:disabled {{ color: {FAINT}; border-color: {BORDER}; background-color: {PANEL2}; }}
QPushButton#Primary {{
    background-color: {ACCENT};
    border: none;
    color: #FFFFFF;
}}
QPushButton#Primary:hover {{ background-color: {ACCENT_DARK}; }}
QPushButton#Primary:disabled {{ background-color: {PANEL2}; color: {FAINT}; }}
QPushButton#Danger:hover {{ border-color: {ERROR}; color: {ERROR}; }}

QToolButton {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 4px 8px;
    font-weight: 600;
}}
QToolButton:hover {{ background-color: {PANEL2}; color: {ACCENT}; }}

QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background-color: {PANEL2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit#Search {{
    border-radius: 18px;
    padding: 7px 16px;
    background-color: {PANEL2};
    border: 1px solid {BORDER};
}}
QLineEdit#Search:focus {{ border: 1px solid {ACCENT}; }}

QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {GRAY};
    margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background-color: {PANEL2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    selection-background-color: {ACCENT};
    selection-color: #FFFFFF;
}}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 17px;
    height: 17px;
    border: 2px solid {BORDER};
    border-radius: 4px;
    background-color: {PANEL2};
}}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    image: none;
}}

QTableWidget {{
    background-color: {CARD};
    alternate-background-color: {PANEL2};
    border: 1px solid {BORDER};
    border-radius: 10px;
    gridline-color: transparent;
}}
QTableWidget::item {{ padding: 6px 8px; border: none; }}
QTableWidget::item:selected {{ background-color: {ACCENT}; color: #FFFFFF; }}
QHeaderView::section {{
    background-color: {SURFACE};
    color: {GRAY};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 9px 8px;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 1px;
}}

QListWidget#Sidebar {{
    background-color: {BG};
    border: none;
    border-radius: 10px;
}}
QListWidget#Sidebar::item {{
    border-radius: 8px;
    padding: 9px 12px;
    margin: 2px 6px;
    color: {GRAY};
}}
QListWidget#Sidebar::item:hover {{
    background-color: {PANEL2};
    color: {TEXT};
}}
QListWidget#Sidebar::item:selected {{
    background-color: {ACCENT};
    color: #FFFFFF;
    font-weight: 700;
}}
QListWidget {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QListWidget::item {{ padding: 4px 6px; }}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {FAINT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: {FAINT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QProgressBar {{
    background-color: {PANEL2};
    border: 1px solid {BORDER};
    border-radius: 5px;
    height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 4px;
}}

QLabel#PageTitle {{
    font-size: 22px;
    font-weight: 800;
    letter-spacing: 0.5px;
    background: transparent;
}}
QLabel#SectionTitle {{
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 2px;
    color: {GRAY};
    background: transparent;
}}
QLabel#Hint {{
    font-size: 12px;
    color: {GRAY};
    background: transparent;
}}
QLabel#StatCaption {{
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: {GRAY};
}}
QLabel#StatValue {{
    font-size: 26px;
    font-weight: 800;
    color: {TEXT};
    background: transparent;
}}
QLabel#StatDelta {{
    font-size: 12px;
    color: {GRAY};
    background: transparent;
}}
QMenu {{
    background-color: {PANEL2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{ padding: 6px 22px; border-radius: 5px; }}
QMenu::item:selected {{ background-color: {ACCENT}; color: #FFFFFF; }}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 5px 8px;
}}
QToolTip {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 6px;
    border-radius: 4px;
}}
QStatusBar {{
    background: {BG};
    color: {GRAY};
    border-top: 1px solid {BORDER};
}}
QStatusBar::item {{ border: none; }}
"""


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

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

class TrackerWorker(QThread):
    done = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, config: Dict[str, Any], fn: Callable, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config
        self._fn = fn

    def run(self) -> None:  # noqa: D102
        try:
            storage = Storage(self._config["paths"]["db"])
            try:
                message = self._fn(storage, self._config) or ""
                if not isinstance(message, str):
                    message = str(message)
                self.done.emit(message)
            finally:
                storage.close()
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.failed.emit(str(exc))


def run_discover(storage: Storage, config: Dict[str, Any]) -> Any:
    """Rescan the member profile for mods/addons/files (runs on the worker)."""
    from tracker import discover_mods

    found = discover_mods(storage, config)
    return f"Found {len(found)} item(s)"


# --------------------------------------------------------------------------
# logging bridge
# --------------------------------------------------------------------------

class LogBridge(QObject):
    line = pyqtSignal(str)


class GuiLogHandler(logging.Handler):
    def __init__(self, bridge: LogBridge) -> None:
        super().__init__()
        self._bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        try:
            message = self.format(record)
            self._bridge.line.emit(message)
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------
# reusable widgets
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


class ChartCard(QFrame):
    """A panel showing one chart PNG, rescaled to fit its column."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self._pixmap: Optional[QPixmap] = None
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setMinimumHeight(180)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.addWidget(self._label)

    def set_image(self, path: Path) -> None:
        self._pixmap = QPixmap(str(path))
        self._path = path
        self.rescale(720)

    def rescale(self, width: int) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            self._label.setText(str(self._path.name))
            return
        h = max(140, int(self._pixmap.height() * width / max(1, self._pixmap.width())))
        self._label.setPixmap(self._pixmap.scaled(
            max(120, width), h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))


class ActivityFeed(QFrame):
    """Sidebar panel listing recent download / comment events."""

    KIND_STYLE = {
        "download": ("⬇", SUCCESS),
        "comment": ("💬", ACCENT),
        "reply": ("↩", WARNING),
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
            icon, color = self.KIND_STYLE.get(kind, ("•", GRAY))
            row = QFrame()
            row.setObjectName("EventRow")
            h = QHBoxLayout(row)
            h.setContentsMargins(8, 6, 8, 6)
            h.setSpacing(8)

            icon_label = QLabel(icon)
            icon_label.setStyleSheet(f"color: {color}; font-size: 14px; background: transparent;")
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

class DashboardPage(QWidget):
    SKIP_CHARTS = {"dashboard.png"}
    CHART_ORDER = [
        "downloads_per_day.png",
        "total_downloads.png",
        "mod_overview.png",
        "comment_activity.png",
    ]
    MIN_COLUMN_WIDTH = 460

    def __init__(self, config: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config
        self._chart_cards: List[ChartCard] = []
        self._current_cols = -1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QHBoxLayout()
        self.title = QLabel("Dashboard")
        self.title.setObjectName("PageTitle")
        self.subtitle = QLabel("Never synced")
        self.subtitle.setObjectName("Hint")
        head_col = QVBoxLayout()
        head_col.setSpacing(2)
        head_col.addWidget(self.title)
        head_col.addWidget(self.subtitle)
        header.addLayout(head_col)
        header.addStretch(1)
        layout.addLayout(header)

        self.stat_grid = QGridLayout()
        self.stat_grid.setSpacing(12)
        self.stat_cards: Dict[str, StatCard] = {}
        for key, caption in [
            ("total", "Total downloads"),
            ("today", "Downloads today"),
            ("week", "This week"),
            ("month", "This month"),
            ("avg", "Average / day"),
            ("comments", "Comments"),
            ("replies", "Replies"),
            ("fastest", "Fastest growing"),
        ]:
            card = StatCard(caption)
            self.stat_cards[key] = card
        for i, key in enumerate(["total", "today", "week", "month"]):
            self.stat_grid.addWidget(self.stat_cards[key], 0, i)
        for i, key in enumerate(["avg", "comments", "replies", "fastest"]):
            self.stat_grid.addWidget(self.stat_cards[key], 1, i)
        layout.addLayout(self.stat_grid)

        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(self._build_charts_section(), 1)
        self.activity = ActivityFeed()
        self.activity.setFixedWidth(320)
        body.addWidget(self.activity)
        layout.addLayout(body, 1)

    def _build_charts_section(self) -> QWidget:
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(8)
        wl.addWidget(section_label("Charts"))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.charts_host = QWidget()
        self.charts_grid = QGridLayout(self.charts_host)
        self.charts_grid.setSpacing(16)
        self.charts_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.charts_host)
        wl.addWidget(self.scroll, 1)
        self.placeholder = QLabel("No charts yet. Click \u201cPoll now\u201d to fetch data.")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setObjectName("Hint")
        self.placeholder.setMinimumHeight(180)
        return wrap

    def refresh(self, storage: Optional[Storage] = None) -> None:
        if storage is not None:
            self._update_stats(storage)
            self.activity.refresh(storage)
        self._reload_charts()

    def reload(self) -> None:
        self._reload_charts()

    def _reload_charts(self) -> None:
        while self.charts_grid.count():
            item = self.charts_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._chart_cards = []
        self._current_cols = -1

        out_dir = Path(self._config["paths"]["output"])
        available = {p.name: p for p in out_dir.glob("*.png") if p.name not in self.SKIP_CHARTS}
        ordered = [available[name] for name in self.CHART_ORDER if name in available]
        ordered += sorted(p for name, p in available.items() if name not in self.CHART_ORDER)

        if not ordered:
            self.charts_grid.addWidget(self.placeholder, 0, 0)
            return

        for png in ordered:
            card = ChartCard()
            card.set_image(png)
            self._chart_cards.append(card)
        self._relayout()

    def _update_stats(self, storage: Storage) -> None:
        s = storage.dashboard_stats()
        today = int(s["today_downloads"] or 0)
        self.stat_cards["total"].set_value(s["total_downloads"], f"▲ +{today:,} today", SUCCESS)
        self.stat_cards["today"].set_value(today, "across all tracked items", GRAY)
        self.stat_cards["week"].set_value(s["week_downloads"], "last 7 days", GRAY)
        self.stat_cards["month"].set_value(s["month_downloads"], f"{s['avg_per_day']} per day", GRAY)
        self.stat_cards["avg"].set_value(s["avg_per_day"], "30-day average", GRAY)
        self.stat_cards["comments"].set_value(s["comments"], f"+{s['replies']} replies", GRAY)
        self.stat_cards["replies"].set_value(s["replies"], "", GRAY)
        if s["fastest_mod"]:
            self.stat_cards["fastest"].set_text(s["fastest_mod"], f"▲ +{s['fastest_delta']:,} this week", SUCCESS)
        else:
            self.stat_cards["fastest"].set_text("—", "no growth yet", GRAY)

        member = storage.meta_get("member_name") or "not set"
        last = storage.meta_get("last_poll")
        self.subtitle.setText(f"Member: {member}   |   Last poll: {last if last else 'never'}")

    def _columns(self) -> int:
        width = self.scroll.viewport().width()
        return 2 if width >= self.MIN_COLUMN_WIDTH * 2 else 1

    def _relayout(self) -> None:
        for i in reversed(range(self.charts_grid.count())):
            self.charts_grid.takeAt(i)
        cols = self._columns()
        self._current_cols = cols
        for i, card in enumerate(self._chart_cards):
            r, c = divmod(i, cols)
            self.charts_grid.addWidget(card, r, c)
        self._rescale()

    def _rescale(self) -> None:
        if not self._chart_cards:
            return
        cols = max(1, self._current_cols)
        width = self.scroll.viewport().width()
        col_width = max(200, (width - (cols - 1) * 16) // cols)
        for card in self._chart_cards:
            card.rescale(col_width)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if not self._chart_cards:
            return
        if self._columns() != self._current_cols:
            self._relayout()
        else:
            self._rescale()


class ModsPage(QWidget):
    open_requested = pyqtSignal(str)
    refresh_requested = pyqtSignal(int)
    favorite_toggled = pyqtSignal(str, bool)
    remove_requested = pyqtSignal(str)
    export_requested = pyqtSignal()

    def __init__(self, config: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config
        self._cards: List[ModCard] = []
        self._filter = ""
        self._sort = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QHBoxLayout()
        head_col = QVBoxLayout()
        head_col.setSpacing(2)
        self.title = QLabel("My Mods")
        self.title.setObjectName("PageTitle")
        self.count_label = QLabel("")
        self.count_label.setObjectName("Hint")
        head_col.addWidget(self.title)
        head_col.addWidget(self.count_label)
        header.addLayout(head_col)
        header.addStretch(1)
        layout.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText("Search mods\u2026")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(260)
        self.search.textChanged.connect(self.apply_filter)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Sort: Downloads", "Sort: Today", "Sort: 7-day growth", "Sort: Name", "Sort: Favorites first"])
        self.sort_combo.currentIndexChanged.connect(lambda _: self._rebuild())
        self.export_btn = QPushButton("Export JSON\u2026")
        self.export_btn.clicked.connect(self.export_requested.emit)
        toolbar.addWidget(self.search)
        toolbar.addWidget(self.sort_combo)
        toolbar.addStretch(1)
        toolbar.addWidget(self.export_btn)
        layout.addLayout(toolbar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.host = QWidget()
        self.host.setStyleSheet("background: transparent;")
        self.flow = FlowLayout(self.host, spacing=12, min_width=320)
        self.scroll.setWidget(self.host)
        layout.addWidget(self.scroll, 1)

        self.placeholder = QLabel(
            "Nothing tracked yet.\n\nAdd mods in Configuration \u2192 Manual mods, or click \u201cRescan profile\u201d "
            "to auto-discover your content."
        )
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setObjectName("Hint")
        self.placeholder.setMinimumHeight(220)
        layout.addWidget(self.placeholder)

    def refresh(self, storage: Storage) -> None:
        self._rebuild(storage)

    def _rebuild(self, storage: Optional[Storage] = None) -> None:
        if storage is not None:
            self._storage = storage
        storage = getattr(self, "_storage", None)
        if storage is None:
            return

        totals = storage.totals_per_mod()
        mods = {int(m["id"]): m for m in storage.get_mods(active_only=True)}

        # per-mod deltas (7-day growth) from snapshots
        deltas: Dict[int, int] = {}
        updated_at: Dict[int, str] = {}
        snaps = storage.snapshots_for_all([int(t["id"]) for t in totals])
        today = datetime.date.today()
        for mod_id, rows in snaps.items():
            daily_max: Dict[datetime.date, int] = {}
            for s in rows:
                try:
                    d = datetime.date.fromisoformat(str(s["fetched_at"])[:10])
                except Exception:  # noqa: BLE001
                    continue
                daily_max[d] = max(daily_max.get(d, 0), int(s["downloads_total"] or 0))
            days = sorted(daily_max)
            delta = 0
            prev = None
            for d in days:
                cur = daily_max[d]
                if prev is not None and (today - d).days < 7:
                    delta += max(0, cur - prev)
                prev = cur
            deltas[mod_id] = delta
            if rows:
                updated_at[mod_id] = str(rows[-1]["fetched_at"])

        self.flow.clear()
        self._cards = []
        for t in totals:
            meta = dict(mods.get(int(t["id"]), {}))
            card = ModCard()
            card.set_data(t, meta, delta_7d=deltas.get(int(t["id"]), 0),
                          updated=updated_at.get(int(t["id"]), ""))
            card.open_requested.connect(self.open_requested)
            card.refresh_requested.connect(self.refresh_requested)
            card.favorite_toggled.connect(self.favorite_toggled)
            card.remove_requested.connect(self.remove_requested)
            card.export_requested.connect(self.export_requested)
            self._cards.append(card)
            self.flow.add_card(card)

        self._apply_sort()
        self._apply_filter()
        self.count_label.setText(f"{len(self._cards)} tracked" + ("  ·  matches filter" if self._filter else ""))

        has_any = bool(self._cards) or bool(storage.get_mods(active_only=True))
        self.scroll.setVisible(has_any)
        self.placeholder.setVisible(not has_any)

    def _apply_sort(self) -> None:
        if self._sort == 0:
            key = _card_downloads
        elif self._sort == 1:
            key = _card_today
        elif self._sort == 2:
            key = _card_growth
        elif self._sort == 3:
            key = lambda c: c._name.text().lower()
        else:
            key = lambda c: (not c._favorite, _card_downloads(c))
        self._cards.sort(key=key, reverse=(self._sort in (0, 1, 2, 4)))
        self.flow.clear()
        for card in self._cards:
            self.flow.add_card(card)

    def apply_filter(self, text: str) -> None:
        self._filter = text
        self._apply_filter()
        if self.count_label.text():
            self.count_label.setText(f"{len(self._cards)} tracked" + ("  ·  matches filter" if text.strip() else ""))

    def _apply_filter(self) -> None:
        needle = self._filter.strip().lower()
        for card in self._cards:
            match = (not needle) or card.matches(self._filter)
            card.setVisible(match)

    def _export(self) -> None:
        self.export_requested.emit()


def _card_downloads(card: ModCard) -> int:
    try:
        return int((card._dl.text() or "0").replace(",", ""))
    except Exception:  # noqa: BLE001
        return 0


def _card_today(card: ModCard) -> int:
    try:
        text = card._dl_cap.text()
        plus = text.split("+")[-1].split(" TODAY")[0].replace(",", "")
        return int(plus or 0)
    except Exception:  # noqa: BLE001
        return 0


def _card_growth(card: ModCard) -> int:
    text = card._growth.text()
    try:
        if "▲" in text:
            return int(text.split("+")[-1].replace(",", "").split()[0])
    except Exception:  # noqa: BLE001
        pass
    return -1 if "— no change" in text else 0


class HistoryPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Download history")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        hint = QLabel("Snapshots over time for the selected item. Delta = change since previous snapshot.")
        hint.setObjectName("Hint")
        layout.addWidget(hint)

        row = QHBoxLayout()
        row.addWidget(QLabel("Item:"))
        self.mod_combo = QComboBox()
        self.mod_combo.currentIndexChanged.connect(lambda _: self._populate())
        row.addWidget(self.mod_combo, 1)
        self.reload_btn = QPushButton("Reload")
        self.reload_btn.clicked.connect(lambda: self.refresh(self._storage))
        row.addWidget(self.reload_btn)
        layout.addLayout(row)

        self.table = make_table(
            ["Fetched", "Downloads", "Today", "Delta", "Visits", "Visits today", "Rank", "Watchers"]
        )
        layout.addWidget(self.table, 1)
        self._storage = None

    def refresh(self, storage: Storage) -> None:
        self._storage = storage
        current = self.mod_combo.currentData()
        self.mod_combo.blockSignals(True)
        self.mod_combo.clear()
        for m in storage.get_mods(active_only=True):
            self.mod_combo.addItem(f"{m['name']}  ({m['content_type']})", int(m["id"]))
        if current is not None:
            idx = self.mod_combo.findData(current)
            if idx >= 0:
                self.mod_combo.setCurrentIndex(idx)
        self.mod_combo.blockSignals(False)
        self._populate()

    def _populate(self) -> None:
        if self._storage is None:
            return
        mod_id = self.mod_combo.currentData()
        if mod_id is None:
            fill_table(self.table, [])
            return
        rows: List[List[Any]] = []
        prev_total = None
        for s in self._storage.snapshots_for(mod_id):
            total = s["downloads_total"]
            delta = ""
            if prev_total is not None and total is not None:
                delta = max(0, int(total) - int(prev_total))
            prev_total = total
            rank = f"{s['rank'] or '-'}/{s['rank_total'] or '-'}" if s["rank"] is not None else "-"
            rows.append([
                s["fetched_at"],
                s["downloads_total"],
                s["downloads_today"],
                delta,
                s["visits"],
                s["visits_today"],
                rank,
                s["watchers"] or 0,
            ])
        fill_table(self.table, rows)


class CommentsPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._filter = ""
        self._rows: List[List[Any]] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Comments & replies")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        hint = QLabel("All comments seen on your tracked items (newest first).")
        hint.setObjectName("Hint")
        layout.addWidget(hint)

        toolbar = QHBoxLayout()
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Filter: All", "Filter: Replies only", "Filter: New comments"])
        self.filter_combo.currentIndexChanged.connect(lambda _: self._apply_filter())
        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText("Search comments\u2026")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(240)
        self.search.textChanged.connect(lambda _: self._apply_filter())
        self.open_btn = QPushButton("Open selected on ModDB")
        self.open_btn.clicked.connect(self._open_selected)
        toolbar.addWidget(self.filter_combo)
        toolbar.addWidget(self.search)
        toolbar.addStretch(1)
        toolbar.addWidget(self.open_btn)
        layout.addLayout(toolbar)

        self.table = make_table(["Posted", "Mod", "Author", "Content"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(lambda _: self._open_selected())
        layout.addWidget(self.table, 1)
        self.placeholder = QLabel("No comments yet. Poll your tracked items to gather them.")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setObjectName("Hint")
        self.placeholder.setMinimumHeight(120)
        layout.addWidget(self.placeholder)
        self._storage = None
        self._mod_urls: Dict[int, str] = {}

    def refresh(self, storage: Storage) -> None:
        self._storage = storage
        self._mod_urls = {}
        for m in storage.get_mods(active_only=False):
            m = dict(m)
            self._mod_urls[int(m["id"])] = str(m.get("url") or "")
        rows: List[List[Any]] = []
        for c in storage.recent_comments(300):
            rows.append([
                c["posted_at"],
                self._mod_name(storage, c["mod_id"]),
                c["author"],
                (c["content"] or "").replace("\n", " ")[:300],
                c["mod_id"],
                c["parent_id"],
            ])
        self._rows = rows
        self._apply_filter()

    @staticmethod
    def _mod_name(storage: Storage, mod_id: int) -> str:
        for m in storage.get_mods(active_only=False):
            if int(m["id"]) == int(mod_id):
                return m["name"]
        return str(mod_id)

    def apply_filter(self, text: str) -> None:
        self.search.setText(text)
        self._apply_filter()

    def _apply_filter(self) -> None:
        needle = self.search.text().strip().lower()
        mode = self.filter_combo.currentIndex()
        out = []
        for row in self._rows:
            is_reply = bool(row[5])
            if mode == 1 and is_reply:
                out.append(row)
            elif mode == 2 and not is_reply:
                out.append(row)
            elif mode == 0:
                out.append(row)
        if needle:
            out = [r for r in out if needle in f"{r[1]} {r[2]} {r[3]}".lower()]
        fill_table(self.table, [r[:4] for r in out])
        self.placeholder.setVisible(not self._rows)
        self.table.setVisible(bool(self._rows))

    def _open_selected(self) -> None:
        idx = self.table.currentRow()
        if idx < 0 or idx >= len(self._rows):
            return
        mod_id = self._rows[idx][4]
        url = self._mod_urls.get(int(mod_id), "")
        if url:
            QDesktopServices.openUrl(QUrl(url))


class EventsPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._filter = ""
        self._rows: List[List[Any]] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Notifications")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        hint = QLabel("Download and comment events detected by polls.")
        hint.setObjectName("Hint")
        layout.addWidget(hint)

        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText("Search events\u2026")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(240)
        self.search.textChanged.connect(lambda _: self._apply_filter())
        toolbar.addWidget(self.search)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.table = make_table(["Time", "Kind", "Mod", "Message"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)
        self.placeholder = QLabel("No events yet. Run a poll to start recording activity.")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setObjectName("Hint")
        self.placeholder.setMinimumHeight(120)
        layout.addWidget(self.placeholder)

    def refresh(self, storage: Storage) -> None:
        rows: List[List[Any]] = []
        for e in storage.recent_events(200):
            rows.append([e["created_at"], e["kind"], e["mod_name"] or "-", e["message"]])
        self._rows = rows
        self._apply_filter()

    def apply_filter(self, text: str) -> None:
        self.search.setText(text)
        self._apply_filter()

    def _apply_filter(self) -> None:
        needle = self.search.text().strip().lower()
        out = self._rows
        if needle:
            out = [r for r in out if needle in f"{r[1]} {r[2]} {r[3]}".lower()]
        fill_table(self.table, out)
        self.placeholder.setVisible(not self._rows)
        self.table.setVisible(bool(self._rows))


class LogPage(QPlainTextEdit):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(3000)
        self.setStyleSheet(
            f"QPlainTextEdit {{ background: {PANEL}; color: {GRAY}; border: 1px solid {BORDER};"
            "border-radius: 8px; font-family: Consolas, monospace; font-size: 12px; }}"
        )


def _merge_defaults(data: Dict[str, Any]) -> Dict[str, Any]:
    """Deep-merge a parsed JSON object over the built-in default config."""
    base = json.loads(json.dumps(tracker.DEFAULT_CONFIG))

    def _merge(b: Dict[str, Any], o: Dict[str, Any]) -> None:
        for key, value in o.items():
            if isinstance(value, dict) and isinstance(b.get(key), dict):
                _merge(b[key], value)
            else:
                b[key] = value

    _merge(base, data)
    return base


class SettingsPage(QWidget):
    saved = pyqtSignal()
    file_reload = pyqtSignal()

    def __init__(self, config: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Configuration")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        hint = QLabel("Everything is edited in-app and saved to config.json.")
        hint.setObjectName("Hint")
        root.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)

        # ---- profile
        layout.addWidget(section_label("Member profile"))
        box = panel(content)
        gl = QGridLayout(box)
        gl.setHorizontalSpacing(12)
        gl.setVerticalSpacing(10)
        gl.addWidget(QLabel("Profile URL:"), 0, 0)
        self.profile = QLineEdit()
        self.profile.setPlaceholderText("https://www.moddb.com/members/yourname")
        gl.addWidget(self.profile, 0, 1)
        self.auto_discover = QCheckBox("Auto-discover mods/addons/files from the profile")
        gl.addWidget(self.auto_discover, 1, 0, 1, 2)
        layout.addWidget(box)

        # ---- manual mods
        layout.addWidget(section_label("Manual mods (tracked in addition to auto-discovered)"))
        box2 = panel(content)
        ml = QVBoxLayout(box2)
        self.mods_list = QListWidget()
        ml.addWidget(self.mods_list)
        mrow = QHBoxLayout()
        self.mod_url_input = QLineEdit()
        self.mod_url_input.setPlaceholderText("https://www.moddb.com/mods/...")
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_mod)
        remove_btn = QPushButton("Remove selected")
        remove_btn.clicked.connect(self._remove_mod)
        mrow.addWidget(self.mod_url_input, 1)
        mrow.addWidget(add_btn)
        mrow.addWidget(remove_btn)
        ml.addLayout(mrow)
        layout.addWidget(box2)

        # ---- polling
        layout.addWidget(section_label("Polling"))
        box3 = panel(content)
        pl = QGridLayout(box3)
        pl.setHorizontalSpacing(12)
        pl.addWidget(QLabel("Interval (minutes):"), 0, 0)
        self.interval = QSpinBox()
        self.interval.setRange(5, 1440)
        self.interval.setSuffix(" min")
        pl.addWidget(self.interval, 0, 1)
        self.charts_each_poll = QCheckBox("Regenerate charts after each poll")
        pl.addWidget(self.charts_each_poll, 1, 0, 1, 2)
        layout.addWidget(box3)

        # ---- notifications
        layout.addWidget(section_label("Notifications"))
        box4 = panel(content)
        nl = QVBoxLayout(box4)
        self.notify_downloads = QCheckBox("New downloads")
        self.notify_comments = QCheckBox("New comments")
        self.notify_replies = QCheckBox("Replies to me")
        nl.addWidget(self.notify_downloads)
        nl.addWidget(self.notify_comments)
        nl.addWidget(self.notify_replies)
        ng = QGridLayout()
        ng.addWidget(QLabel("Max toasts per poll:"), 0, 0)
        self.max_toasts = QSpinBox()
        self.max_toasts.setRange(1, 20)
        ng.addWidget(self.max_toasts, 0, 1)
        ng.addWidget(QLabel("Toast app id:"), 1, 0)
        self.app_id = QLineEdit()
        ng.addWidget(self.app_id, 1, 1)
        nl.addLayout(ng)
        layout.addWidget(box4)

        # ---- tray
        layout.addWidget(section_label("System tray"))
        box5 = panel(content)
        tl = QVBoxLayout(box5)
        self.close_to_tray = QCheckBox("Minimize to tray when closing the window")
        self.start_minimized = QCheckBox("Start hidden in the tray (background mode)")
        tl.addWidget(self.close_to_tray)
        tl.addWidget(self.start_minimized)
        th = QLabel("The app keeps polling and showing toasts while it sits in the tray.")
        th.setObjectName("Hint")
        tl.addWidget(th)
        layout.addWidget(box5)

        # ---- paths
        layout.addWidget(section_label("Paths"))
        box6 = panel(content)
        pg = QGridLayout(box6)
        pg.setHorizontalSpacing(12)
        pg.addWidget(QLabel("Database:"), 0, 0)
        self.path_db = QLineEdit()
        pg.addWidget(self.path_db, 0, 1)
        pg.addWidget(QLabel("Charts output:"), 1, 0)
        self.path_output = QLineEdit()
        pg.addWidget(self.path_output, 1, 1)
        pg.addWidget(QLabel("Logs:"), 2, 0)
        self.path_logs = QLineEdit()
        pg.addWidget(self.path_logs, 2, 1)
        layout.addWidget(box6)

        # ---- advanced JSON
        layout.addWidget(section_label("Advanced"))
        box7 = panel(content)
        al = QVBoxLayout(box7)
        self.json_toggle = QCheckBox("Edit config.json as raw JSON")
        self.json_toggle.toggled.connect(self._toggle_json)
        al.addWidget(self.json_toggle)
        self.json_editor = QPlainTextEdit()
        self.json_editor.setMaximumHeight(240)
        self.json_editor.setStyleSheet(
            f"QPlainTextEdit {{ background: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER};"
            "border-radius: 6px; font-family: Consolas, monospace; font-size: 12px; }}"
        )
        al.addWidget(self.json_editor)
        self.json_editor.hide()
        aj = QHBoxLayout()
        self.apply_json_btn = QPushButton("Apply JSON to form")
        self.apply_json_btn.clicked.connect(self._apply_json)
        aj.addWidget(self.apply_json_btn)
        aj.addStretch(1)
        al.addLayout(aj)
        self.apply_json_btn.hide()
        layout.addWidget(box7)

        layout.addStretch(1)

        # ---- buttons
        buttons = QHBoxLayout()
        self.save_btn = QPushButton("Save configuration")
        self.save_btn.setObjectName("Primary")
        self.save_btn.clicked.connect(self._save)
        self.reload_btn = QPushButton("Reload from file")
        self.reload_btn.clicked.connect(self._reload_from_file)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.reload_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self.reload()

    # ---- helpers --------------------------------------------------------
    def _add_mod(self) -> None:
        url = self.mod_url_input.text().strip()
        if not url:
            return
        existing = [self.mods_list.item(i).text() for i in range(self.mods_list.count())]
        if url not in existing:
            self.mods_list.addItem(url)
        self.mod_url_input.clear()

    def _remove_mod(self) -> None:
        for item in self.mods_list.selectedItems():
            self.mods_list.takeItem(self.mods_list.row(item))

    def _toggle_json(self, checked: bool) -> None:
        self.json_editor.setVisible(checked)
        self.apply_json_btn.setVisible(checked)
        if checked:
            self.json_editor.setPlainText(json.dumps(self.current_config(), indent=2))

    def _apply_json(self) -> None:
        try:
            parsed = json.loads(self.json_editor.toPlainText())
            if not isinstance(parsed, dict):
                raise ValueError("Root value must be a JSON object")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Invalid JSON", str(exc))
            return
        merged = _merge_defaults(parsed)
        self._config = merged
        self.reload()
        self.json_editor.setPlainText(json.dumps(merged, indent=2))
        QMessageBox.information(self, "Applied", "JSON applied to the form. Review and press Save.")

    def _reload_from_file(self) -> None:
        try:
            self._config = load_config(CONFIG_FILE)
            self.reload()
            self.file_reload.emit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Reload failed", str(exc))

    # ---- data -----------------------------------------------------------
    def reload(self) -> None:
        self.profile.setText(self._config.get("profile_url", ""))
        self.auto_discover.setChecked(bool(self._config.get("auto_discover", True)))
        self.mods_list.clear()
        for url in self._config.get("mods", []):
            if url:
                self.mods_list.addItem(url)
        self.interval.setValue(int(self._config["poll"].get("interval_minutes", 30)))
        self.charts_each_poll.setChecked(bool(self._config["poll"].get("charts_each_poll", True)))
        self.notify_downloads.setChecked(bool(self._config["poll"].get("notify_on_downloads", True)))
        self.notify_comments.setChecked(bool(self._config["poll"].get("notify_on_comments", True)))
        self.notify_replies.setChecked(bool(self._config["poll"].get("notify_on_replies", True)))
        self.max_toasts.setValue(int(self._config["notifications"].get("max_toasts", 5)))
        self.app_id.setText(self._config["notifications"].get("app_id", "ModDB Tracker"))
        self.close_to_tray.setChecked(bool(self._config.get("tray", {}).get("close_to_tray", True)))
        self.start_minimized.setChecked(bool(self._config.get("tray", {}).get("start_minimized", False)))
        self.path_db.setText(self._config["paths"].get("db", "tracker.db"))
        self.path_output.setText(self._config["paths"].get("output", "output"))
        self.path_logs.setText(self._config["paths"].get("logs", "logs"))
        if self.json_editor.isVisible():
            self.json_editor.setPlainText(json.dumps(self.current_config(), indent=2))

    def current_config(self) -> Dict[str, Any]:
        cfg = json.loads(json.dumps(self._config))
        cfg["profile_url"] = self.profile.text().strip()
        cfg["auto_discover"] = self.auto_discover.isChecked()
        cfg["mods"] = [self.mods_list.item(i).text().strip() for i in range(self.mods_list.count()) if self.mods_list.item(i).text().strip()]
        cfg["poll"]["interval_minutes"] = self.interval.value()
        cfg["poll"]["charts_each_poll"] = self.charts_each_poll.isChecked()
        cfg["poll"]["notify_on_downloads"] = self.notify_downloads.isChecked()
        cfg["poll"]["notify_on_comments"] = self.notify_comments.isChecked()
        cfg["poll"]["notify_on_replies"] = self.notify_replies.isChecked()
        cfg["notifications"]["max_toasts"] = self.max_toasts.value()
        cfg["notifications"]["app_id"] = self.app_id.text().strip() or "ModDB Tracker"
        cfg["tray"]["close_to_tray"] = self.close_to_tray.isChecked()
        cfg["tray"]["start_minimized"] = self.start_minimized.isChecked()
        cfg["paths"]["db"] = self.path_db.text().strip() or "tracker.db"
        cfg["paths"]["output"] = self.path_output.text().strip() or "output"
        cfg["paths"]["logs"] = self.path_logs.text().strip() or "logs"
        return cfg

    def _save(self) -> None:
        try:
            save_config(self.current_config(), CONFIG_FILE)
            QMessageBox.information(self, "Saved", "Configuration saved to config.json")
            self.saved.emit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save failed", str(exc))


# --------------------------------------------------------------------------
# main window
# --------------------------------------------------------------------------

class TrackerWindow(QMainWindow):
    NAV = [
        ("Dashboard", "🏠"),
        ("My Mods", "📦"),
        ("History", "📈"),
        ("Comments", "💬"),
        ("Notifications", "🔔"),
        ("Configuration", "⚙️"),
        ("Log", "🪵"),
    ]

    def __init__(self, config_path: str = CONFIG_FILE) -> None:
        super().__init__()
        self.config_path = config_path
        self.config = load_config(config_path)
        transport.patch_moddb()  # ensure moddb's internal get_page is Cloudflare-proof
        self.storage = Storage(self.config["paths"]["db"])
        self.worker: Optional[TrackerWorker] = None
        self._stopping = False
        self._quit_requested = False
        self._tray_hint_shown = False
        self.tray: Optional[QSystemTrayIcon] = None

        self.setWindowTitle("ModDB Tracker")
        self.resize(1280, 820)
        self.setMinimumSize(1080, 680)

        self._build_ui()
        self._wire_logging()
        self._build_tray()

        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self._poll_now)
        self.auto_checkbox = QCheckBox("Auto-poll")
        self.auto_checkbox.toggled.connect(self._toggle_auto_poll)
        self.statusBar().addWidget(self.auto_checkbox)
        self.busy_bar = QProgressBar()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setFixedWidth(120)
        self.busy_bar.setVisible(False)
        self.statusBar().addWidget(self.busy_bar)

        self.status_label = QLabel("")
        self.statusBar().addPermanentWidget(self.status_label)

        self._db_label = QLabel("")
        self.statusBar().addPermanentWidget(self._db_label)

        self.refresh_all()
        self.set_status("Ready. Click \u201cPoll now\u201d to fetch data.")

    # ---- ui construction ------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_top_bar())

        body = QHBoxLayout()
        body.setContentsMargins(14, 14, 14, 12)
        body.setSpacing(14)
        body.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        self.dashboard = DashboardPage(self.config)
        self.mods = ModsPage(self.config)
        self.history = HistoryPage()
        self.comments = CommentsPage()
        self.events = EventsPage()
        self.log_page = LogPage()
        self.settings = SettingsPage(self.config)
        for page in (self.dashboard, self.mods, self.history, self.comments, self.events, self.settings, self.log_page):
            self.stack.addWidget(page)
        self.settings.saved.connect(self._on_settings_saved)
        self.settings.file_reload.connect(self._on_settings_saved)
        self.mods.open_requested.connect(self._open_url)
        self.mods.refresh_requested.connect(self._refresh_mod)
        self.mods.favorite_toggled.connect(self._toggle_favorite)
        self.mods.remove_requested.connect(self._remove_mod)
        self.mods.export_requested.connect(self._export_all)
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)

        self.setCentralWidget(central)
        self.sidebar.setCurrentRow(0)

    def _build_top_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("TopBar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(18, 10, 18, 10)
        h.setSpacing(12)

        logo = QLabel()
        logo.setPixmap(QIcon(tray_icon_path()).pixmap(30, 30))
        logo.setFixedSize(30, 30)
        title = QLabel("ModDB Tracker")
        title.setStyleSheet("font-size: 16px; font-weight: 800; letter-spacing: 0.5px;")
        version = QLabel(f"v{VERSION}")
        version.setStyleSheet(
            f"color: {ACCENT}; font-size: 10px; font-weight: 700; background: {ACCENT}22;"
            "padding: 2px 7px; border-radius: 8px;"
        )
        brand = QHBoxLayout()
        brand.setSpacing(8)
        brand.addWidget(logo)
        brand.addWidget(title)
        brand.addWidget(version, 0, Qt.AlignmentFlag.AlignVCenter)
        h.addLayout(brand)

        h.addStretch(1)

        self.search_box = QLineEdit()
        self.search_box.setObjectName("Search")
        self.search_box.setPlaceholderText("Search mods, comments, events\u2026")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setFixedWidth(280)
        self.search_box.textChanged.connect(self._search_changed)
        h.addWidget(self.search_box)

        self.sync_label = QLabel("Not synced")
        self.sync_label.setStyleSheet(f"color: {GRAY}; font-size: 12px;")
        h.addWidget(self.sync_label)

        self.poll_btn = QPushButton("Poll now")
        self.poll_btn.setObjectName("Primary")
        self.poll_btn.clicked.connect(self._poll_now)
        self.rescan_btn = QPushButton("Rescan")
        self.rescan_btn.clicked.connect(self._rescan)
        self.charts_btn = QPushButton("Charts")
        self.charts_btn.clicked.connect(self._regenerate_charts)
        self.refresh_btn = QPushButton("⟳ Refresh")
        self.refresh_btn.clicked.connect(self.refresh_all)
        h.addWidget(self.poll_btn)
        h.addWidget(self.rescan_btn)
        h.addWidget(self.charts_btn)
        h.addWidget(self.refresh_btn)
        return bar

    def _build_sidebar(self) -> QWidget:
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(200)
        for name, icon in self.NAV:
            item = QListWidgetItem(f"{icon}   {name}")
            item.setSizeHint(QSize(0, 38))
            self.sidebar.addItem(item)
        self.sidebar.currentRowChanged.connect(self._nav_changed)
        return self.sidebar

    def _nav_changed(self, row: int) -> None:
        self.stack.setCurrentIndex(row)

    # ---- system tray ----------------------------------------------------
    def _build_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(QIcon(tray_icon_path()), self)
        self.tray.setToolTip("ModDB Tracker")

        menu = QMenu()
        self.tray_menu_show = QAction("Show / Hide", self)
        self.tray_menu_show.triggered.connect(self._toggle_window)
        self.tray_menu_poll = QAction("Poll now", self)
        self.tray_menu_poll.triggered.connect(self._poll_now)
        self.tray_menu_rescan = QAction("Rescan profile", self)
        self.tray_menu_rescan.triggered.connect(self._rescan)
        self.tray_menu_quit = QAction("Quit", self)
        self.tray_menu_quit.triggered.connect(self._request_quit)
        menu.addAction(self.tray_menu_show)
        menu.addAction(self.tray_menu_poll)
        menu.addAction(self.tray_menu_rescan)
        menu.addSeparator()
        menu.addAction(self.tray_menu_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_window()

    def _toggle_window(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def hide_to_tray(self, first_time: bool = False) -> None:
        if self.tray is None:
            return
        self.hide()
        if first_time or not self._tray_hint_shown:
            self._tray_hint_shown = True
            self.tray.showMessage(
                "ModDB Tracker",
                "Still running in the background. Polling and notifications stay active.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )

    def _request_quit(self) -> None:
        self._quit_requested = True
        if self.tray is not None:
            self.tray.hide()
        self.close()

    def closeEvent(self, event) -> None:  # noqa: N802
        tray_active = self.tray is not None and self.config.get("tray", {}).get("close_to_tray", True)
        if not self._quit_requested and tray_active:
            event.ignore()
            self.hide_to_tray()
            return
        self._stopping = True
        self.auto_timer.stop()
        if self.worker is not None and self.worker.isRunning():
            self.worker.wait(5000)
        self.storage.close()
        event.accept()

    # ---- logging --------------------------------------------------------
    def _wire_logging(self) -> None:
        self._bridge = LogBridge(self)
        self._bridge.line.connect(self.log_page.appendPlainText)
        handler = GuiLogHandler(self._bridge)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
        logging.getLogger().addHandler(handler)

    # ---- data -----------------------------------------------------------
    def refresh_all(self) -> None:
        self.dashboard.refresh(self.storage)
        self.mods.refresh(self.storage)
        self.history.refresh(self.storage)
        self.comments.refresh(self.storage)
        self.events.refresh(self.storage)
        self.settings.reload()

        member = self.storage.meta_get("member_name") or ""
        last = self.storage.meta_get("last_poll") or ""
        bits = [f"Member: {member}"] if member else ["Member: not set"]
        bits.append(f"Last poll: {last}" if last else "Never polled")
        self.status_label.setText("   |   ".join(bits))
        self.sync_label.setText(f"Synced {relative_time(last)}" if last else "Not synced")
        self._update_tray_tooltip(member, last)

        try:
            db_path = Path(self.storage.db_path) if hasattr(self.storage, "db_path") else Path(self.config["paths"]["db"])
            size_mb = db_path.stat().st_size / (1024 * 1024) if db_path.exists() else 0
            self._db_label.setText(f"DB {size_mb:.1f} MB")
        except Exception:  # noqa: BLE001
            pass

    def _on_settings_saved(self) -> None:
        self.config = load_config(self.config_path)
        self.storage = Storage(self.config["paths"]["db"])
        self.dashboard._config = self.config
        self.mods._config = self.config
        self._restart_auto_timer()
        self.refresh_all()

    def _open_url(self, url: str) -> None:
        if url:
            QDesktopServices.openUrl(QUrl(url))

    # ---- actions --------------------------------------------------------
    def _set_busy(self, busy: bool, label: str = "") -> None:
        self.poll_btn.setEnabled(not busy)
        self.rescan_btn.setEnabled(not busy)
        self.charts_btn.setEnabled(not busy)
        self.refresh_btn.setEnabled(not busy)
        self.busy_bar.setVisible(busy)
        if busy:
            self.set_status(label or "Working...")

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
        if self.tray is not None:
            self.tray.setToolTip(f"ModDB Tracker\n{text}")

    def _update_tray_tooltip(self, member: str, last: str) -> None:
        if self.tray is None:
            return
        line = f"Member: {member or 'not set'}   Last poll: {last or 'never'}"
        self.tray.setToolTip(f"ModDB Tracker\n{line}")

    def _on_worker_done(self, message: str) -> None:
        self._set_busy(False)
        self.refresh_all()
        self.set_status("Done.")
        if message:
            logger.info("Worker finished: %s", message)

    def _on_worker_failed(self, message: str) -> None:
        self._set_busy(False)
        self.refresh_all()
        self.set_status("Failed.")
        QMessageBox.critical(self, "Task failed", message)

    def _start_worker(self, fn: Callable, label: str) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        self._set_busy(True, label)
        self.worker = TrackerWorker(self.config, fn, parent=self)
        self.worker.done.connect(self._on_worker_done)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.start()

    def _poll_now(self) -> None:
        self._start_worker(run_poll, "Polling ModDB...")

    def _rescan(self) -> None:
        self._start_worker(run_discover, "Scanning profile...")

    def _regenerate_charts(self) -> None:
        def _charts(storage: Storage, config: Dict[str, Any]) -> Any:
            import charts

            paths = charts.generate_all(storage, Path(config["paths"]["output"]))
            return f"{len(paths)} chart(s) written"

        self._start_worker(_charts, "Regenerating charts...")

    # ---- per-mod actions ------------------------------------------------
    def _refresh_mod(self, mod_id: int) -> None:
        mod = next((dict(m) for m in self.storage.get_mods(active_only=True) if int(m["id"]) == int(mod_id)), None)
        if mod is None:
            return

        def _one(storage: Storage, config: Dict[str, Any]) -> str:
            target = next((dict(m) for m in storage.get_mods(active_only=True) if int(m["id"]) == int(mod_id)), None)
            if target is None:
                return "mod not found"
            tracker.snapshot_mod(storage, target, config, notify=False)
            return f"Refreshed {target['name']}"

        self._start_worker(_one, f"Refreshing {mod['name']}...")

    def _toggle_favorite(self, name_id: str, favorite: bool) -> None:
        self.storage.set_mod_favorite(name_id, favorite)
        self.refresh_all()

    def _remove_mod(self, name_id: str) -> None:
        mod = next((dict(m) for m in self.storage.get_mods(active_only=False) if str(m["name_id"]) == name_id), None)
        name = mod["name"] if mod else name_id
        answer = QMessageBox.question(
            self,
            "Remove from tracking",
            f"Stop tracking \u201c{name}\u201d?\nExisting history is kept, it just won't be polled anymore.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.storage.set_mod_active(name_id, False)
            self.refresh_all()

    def _export_all(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export data", "moddb_tracker_export.json", "JSON (*.json)")
        if not path:
            return
        try:
            storage = Storage(self.config["paths"]["db"])
            try:
                storage.export_json(path)
            finally:
                storage.close()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Export failed", str(exc))

    # ---- search ---------------------------------------------------------
    def _search_changed(self, text: str) -> None:
        page = self.stack.currentWidget()
        if hasattr(page, "apply_filter"):
            page.apply_filter(text)

    # ---- auto poll ------------------------------------------------------
    def _toggle_auto_poll(self, checked: bool) -> None:
        if checked:
            self.auto_timer.start(self._auto_interval_ms())
            self.set_status(f"Auto-poll every {self.config['poll']['interval_minutes']} min.")
        else:
            self.auto_timer.stop()
            self.set_status("Auto-poll off.")

    def _auto_interval_ms(self) -> int:
        return max(60, int(self.config["poll"]["interval_minutes"]) * 60 * 1000)

    def _restart_auto_timer(self) -> None:
        if self.auto_timer.isActive():
            self.auto_timer.start(self._auto_interval_ms())


def main() -> int:
    parser = argparse.ArgumentParser(description="ModDB Tracker GUI")
    parser.add_argument("--config", default=CONFIG_FILE, help="path to config.json")
    parser.add_argument("--minimized", action="store_true", help="start hidden in the system tray")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    transport.patch_moddb()
    window = TrackerWindow(args.config)

    if QSystemTrayIcon.isSystemTrayAvailable():
        app.setQuitOnLastWindowClosed(False)  # closing the window keeps the app in the tray
        if args.minimized or window.config.get("tray", {}).get("start_minimized", False):
            window.hide_to_tray(first_time=True)
            return app.exec()
        window.show()
    else:
        window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
