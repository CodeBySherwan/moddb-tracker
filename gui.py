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
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import QObject, QThread, Qt, QTimer, QUrl, pyqtSignal
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
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import transport
from storage import Storage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tracker import (  # noqa: E402  (imports depend on sys.path above)
    CONFIG_FILE,
    discover_mods,
    load_config,
    run_init,
    run_poll,
    save_config,
)

logger = logging.getLogger("tracker.gui")

# palette matching the matplotlib theme
BG = "#121417"
PANEL = "#1c1f24"
PANEL2 = "#23272e"
BORDER = "#2f343d"
TEXT = "#e8eaed"
GRAY = "#9aa0a6"
ACCENT = "#f0c040"


def tray_icon_path() -> str:
    """Generate (once) a small tray icon next to gui.py and return its path."""
    path = Path(__file__).resolve().parent / "tray_icon.png"
    if path.exists():
        return str(path)
    size = 96
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(ACCENT))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 4, size - 8, size - 8, 18, 18)
    font = QFont("Arial", 24, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor("#1a1a1a"))
    painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "MDB")
    painter.end()
    pm.save(str(path))
    return str(path)

QSS = f"""
QWidget {{ background: {BG}; color: {TEXT}; font-size: 13px; }}
QMainWindow, QDialog {{ background: {BG}; }}
QFrame#Panel, QWidget#Panel {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px; }}
QLabel#PageTitle {{ font-size: 20px; font-weight: bold; color: {ACCENT}; }}
QLabel#Hint {{ color: {GRAY}; }}
QPushButton {{
    background: {PANEL2}; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 6px 14px; color: {TEXT};
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:disabled {{ color: #555b66; border-color: {BORDER}; }}
QPushButton#Primary {{ background: {ACCENT}; color: #1a1a1a; font-weight: bold; }}
QPushButton#Primary:hover {{ background: #ffd968; }}
QPushButton#Danger {{ color: #ff7b6b; }}
QListWidget {{
    background: {PANEL}; border: none; border-radius: 8px; padding: 6px; outline: none;
}}
QListWidget::item {{ padding: 10px 12px; border-radius: 6px; margin: 2px; }}
QListWidget::item:selected {{ background: {ACCENT}; color: #1a1a1a; font-weight: bold; }}
QListWidget::item:hover:!selected {{ background: {PANEL2}; }}
QTableWidget {{
    background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px;
    gridline-color: {BORDER}; alternate-background-color: {PANEL2}; selection-background-color: #3a3f48;
}}
QHeaderView::section {{ background: {PANEL2}; color: {ACCENT}; border: none; padding: 6px; font-weight: bold; }}
QLineEdit, QSpinBox, QComboBox {{
    background: {PANEL2}; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 8px;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {BORDER}; border-radius: 4px; background: {PANEL2}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QScrollArea {{ border: none; background: transparent; }}
QStatusBar {{ background: {PANEL}; color: {GRAY}; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 8px; background: {PANEL}; }}
QTabBar::tab {{ background: {PANEL2}; padding: 6px 12px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; }}
QTabBar::tab:selected {{ background: {ACCENT}; color: #1a1a1a; font-weight: bold; }}
"""


# --------------------------------------------------------------------------
# worker thread
# --------------------------------------------------------------------------

class TrackerWorker(QThread):
    """Runs a blocking callable (poll/init/discover) off the UI thread.

    The worker opens its own Storage connection so SQLite's single-thread
    default doesn't trip over the UI's connection.
    """

    done = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, config: Dict[str, Any], fn: Callable[[Storage, Dict[str, Any]], Any],
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._config = config
        self._fn = fn

    def run(self) -> None:
        storage = Storage(self._config["paths"]["db"])
        try:
            result = self._fn(storage, self._config)
            self.done.emit(str(result) if result is not None else "")
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}")
        finally:
            storage.close()


def run_discover(storage: Storage, config: Dict[str, Any]) -> Any:
    return discover_mods(storage, config)


class LogBridge(QObject):
    """Forwards logging records from any thread to the UI (queued delivery)."""

    line = pyqtSignal(str)


class GuiLogHandler(logging.Handler):
    def __init__(self, bridge: LogBridge) -> None:
        super().__init__()
        self._bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._bridge.line.emit(msg)
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------
# widgets
# --------------------------------------------------------------------------

def panel(parent: QWidget) -> QFrame:
    frame = QFrame(parent)
    frame.setObjectName("Panel")
    return frame


def make_table(headers: List[str], selectable: bool = True) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    table.setShowGrid(False)
    table.setSortingEnabled(True)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setStretchLastSection(True)
    if not selectable:
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    return table


def fill_table(table: QTableWidget, rows: List[List[Any]]) -> None:
    table.setSortingEnabled(False)
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            item = QTableWidgetItem("" if value is None else str(value))
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                if c == 0 or isinstance(value, str)
                else Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            table.setItem(r, c, item)
    table.setSortingEnabled(True)


# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------

class DashboardPage(QWidget):
    def __init__(self, config: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config
        layout = QVBoxLayout(self)
        title = QLabel("Dashboard")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        layout.addWidget(self._hint())

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.charts_host = QWidget()
        self.charts_layout = QVBoxLayout(self.charts_host)
        self.charts_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.charts_layout.setSpacing(16)
        self.scroll.setWidget(self.charts_host)
        layout.addWidget(self.scroll, 1)

        self.placeholder = QLabel("No charts yet. Click \"Poll now\" to fetch data.")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setObjectName("Hint")
        self.placeholder.setMinimumHeight(200)

    def _hint(self) -> QLabel:
        hint = QLabel("Charts from output/ -- generated on each poll.")
        hint.setObjectName("Hint")
        return hint

    def reload(self) -> None:
        # clear existing image widgets
        while self.charts_layout.count():
            item = self.charts_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        out_dir = Path(self._config["paths"]["output"])
        pngs = sorted(out_dir.glob("*.png"))
        if not pngs:
            self.charts_layout.addWidget(self.placeholder)
            return

        for png in pngs:
            label = QLabel()
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setPixmap(QPixmap(str(png)))
            label.setProperty("pixmap_path", str(png))
            self.charts_layout.addWidget(label)
            self.charts_layout.setAlignment(label, Qt.AlignmentFlag.AlignCenter)

        self._rescale()  # scale images to fit width

    def _rescale(self) -> None:
        width = max(200, self.scroll.viewport().width() - 40)
        for i in range(self.charts_layout.count()):
            item = self.charts_layout.itemAt(i)
            if item is None or item.widget() is None:
                continue
            label = item.widget()
            path = label.property("pixmap_path")
            if not path:
                continue
            pm = QPixmap(str(path))
            if not pm.isNull():
                label.setPixmap(pm.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._rescale()


class ModsPage(QWidget):
    url_double_clicked = pyqtSignal(str)

    def __init__(self, config: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config
        layout = QVBoxLayout(self)
        title = QLabel("Tracked mods")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        layout.addWidget(self._hint())
        self.table = make_table(
            ["Name", "Type", "Downloads", "Today", "Visits", "Visits today", "Watchers", "Rating", "Rank", "URL"]
        )
        self.table.doubleClicked.connect(self._on_double_clicked)
        layout.addWidget(self.table, 1)
        btn_row = QHBoxLayout()
        self.export_btn = QPushButton("Export JSON...")
        self.export_btn.clicked.connect(self._export)
        btn_row.addWidget(self.export_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

    def _hint(self) -> QLabel:
        hint = QLabel("Latest snapshot per item. Double-click a row to open its page.")
        hint.setObjectName("Hint")
        return hint

    def _rows(self, totals: List[Dict[str, Any]], mods: List[Any]) -> List[List[Any]]:
        by_id = {int(m["id"]): m for m in mods}
        rows = []
        for t in totals:
            m = by_id.get(int(t["id"]), {})
            rank = f"{t['rank'] or '-'}/{t['rank_total'] or '-'}"
            rows.append([
                t["name"],
                m["content_type"] if m else "mod",
                t["downloads_total"],
                t["downloads_today"],
                t["visits"],
                t["visits_today"],
                t["watchers"] or 0,
                t["rating"] if t["rating"] is not None else "-",
                rank,
                t["url"],
            ])
        return rows

    def refresh(self, storage: Storage) -> None:
        totals = storage.totals_per_mod()
        mods = storage.get_mods(active_only=True)
        fill_table(self.table, self._rows(totals, mods))

    def _on_double_clicked(self, index) -> None:
        row = index.row()
        url_item = self.table.item(row, 9)
        if url_item and url_item.text():
            self.url_double_clicked.emit(url_item.text())

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export data", "moddb_tracker_export.json", "JSON (*.json)")
        if path:
            try:
                from storage import Storage
                storage = Storage(self._config["paths"]["db"])
                try:
                    storage.export_json(path)
                finally:
                    storage.close()
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "Export failed", str(exc))


class HistoryPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
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
        layout = QVBoxLayout(self)
        title = QLabel("Comments & replies")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        hint = QLabel("All comments seen on your tracked items (newest first).")
        hint.setObjectName("Hint")
        layout.addWidget(hint)
        self.table = make_table(["Posted", "Mod", "Author", "Content"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

    def refresh(self, storage: Storage) -> None:
        rows: List[List[Any]] = []
        for c in storage.recent_comments(200):
            rows.append([
                c["posted_at"],
                self._mod_name(storage, c["mod_id"]),
                c["author"],
                (c["content"] or "").replace("\n", " ")[:300],
            ])
        fill_table(self.table, rows)

    @staticmethod
    def _mod_name(storage: Storage, mod_id: int) -> str:
        for m in storage.get_mods(active_only=False):
            if int(m["id"]) == int(mod_id):
                return m["name"]
        return str(mod_id)


class EventsPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("Notifications / events")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        hint = QLabel("Download and comment events detected by polls.")
        hint.setObjectName("Hint")
        layout.addWidget(hint)
        self.table = make_table(["Time", "Kind", "Mod", "Message"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

    def refresh(self, storage: Storage) -> None:
        rows: List[List[Any]] = []
        for e in storage.recent_events(200):
            rows.append([e["created_at"], e["kind"], e["mod_name"] or "-", e["message"]])
        fill_table(self.table, rows)


class LogPage(QPlainTextEdit):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(3000)
        self.setStyleSheet(
            f"QPlainTextEdit {{ background: {PANEL}; color: {GRAY}; border: 1px solid {BORDER};"
            "border-radius: 8px; font-family: Consolas, monospace; font-size: 12px; }}"
        )


class SettingsPage(QWidget):
    saved = pyqtSignal()

    def __init__(self, config: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config
        layout = QVBoxLayout(self)
        title = QLabel("Settings")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.profile = QLineEdit()
        self.auto_discover = QCheckBox("Auto-discover mods from profile")
        self.interval = QSpinBox()
        self.interval.setRange(5, 1440)
        self.interval.setSuffix(" min")
        self.notify_downloads = QCheckBox("New downloads")
        self.notify_comments = QCheckBox("New comments")
        self.notify_replies = QCheckBox("Replies to me")
        self.charts_each_poll = QCheckBox("Regenerate charts after each poll")
        self.max_toasts = QSpinBox()
        self.max_toasts.setRange(1, 20)
        self.app_id = QLineEdit()

        form.addWidget(QLabel("Member profile URL:"), 0, 0)
        form.addWidget(self.profile, 0, 1)
        form.addWidget(self.auto_discover, 1, 0, 1, 2)
        form.addWidget(QLabel("Poll interval:"), 2, 0)
        form.addWidget(self.interval, 2, 1)

        section = QLabel("Notifications")
        section.setObjectName("PageTitle")
        layout.addWidget(section)
        layout.addLayout(form)

        notify_box = panel(self)
        nl = QVBoxLayout(notify_box)
        nl.addWidget(self.notify_downloads)
        nl.addWidget(self.notify_comments)
        nl.addWidget(self.notify_replies)
        nl.addWidget(self.charts_each_poll)
        nt = QGridLayout()
        nt.addWidget(QLabel("Max toasts per poll:"), 0, 0)
        nt.addWidget(self.max_toasts, 0, 1)
        nt.addWidget(QLabel("Toast app id:"), 1, 0)
        nt.addWidget(self.app_id, 1, 1)
        nl.addLayout(nt)
        layout.addWidget(notify_box)

        section2 = QLabel("System tray")
        section2.setObjectName("PageTitle")
        layout.addWidget(section2)

        tray_box = panel(self)
        tl = QVBoxLayout(tray_box)
        self.close_to_tray = QCheckBox("Minimize to tray when closing the window")
        self.start_minimized = QCheckBox("Start hidden in the tray (background mode)")
        tl.addWidget(self.close_to_tray)
        tl.addWidget(self.start_minimized)
        hint = QLabel("The app keeps polling and showing toasts while it sits in the tray.")
        hint.setObjectName("Hint")
        tl.addWidget(hint)
        layout.addWidget(tray_box)

        layout.addStretch(1)

        buttons = QHBoxLayout()
        self.save_btn = QPushButton("Save settings")
        self.save_btn.setObjectName("Primary")
        self.save_btn.clicked.connect(self._save)
        self.open_config_btn = QPushButton("Open config.json...")
        self.open_config_btn.clicked.connect(self._open_config)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.open_config_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.reload()

    def reload(self) -> None:
        self.profile.setText(self._config.get("profile_url", ""))
        self.auto_discover.setChecked(bool(self._config.get("auto_discover", True)))
        self.interval.setValue(int(self._config["poll"].get("interval_minutes", 30)))
        self.notify_downloads.setChecked(bool(self._config["poll"].get("notify_on_downloads", True)))
        self.notify_comments.setChecked(bool(self._config["poll"].get("notify_on_comments", True)))
        self.notify_replies.setChecked(bool(self._config["poll"].get("notify_on_replies", True)))
        self.charts_each_poll.setChecked(bool(self._config["poll"].get("charts_each_poll", True)))
        self.max_toasts.setValue(int(self._config["notifications"].get("max_toasts", 5)))
        self.app_id.setText(self._config["notifications"].get("app_id", "ModDB Tracker"))
        self.close_to_tray.setChecked(bool(self._config.get("tray", {}).get("close_to_tray", True)))
        self.start_minimized.setChecked(bool(self._config.get("tray", {}).get("start_minimized", False)))

    def current_config(self) -> Dict[str, Any]:
        cfg = json.loads(json.dumps(self._config))
        cfg["profile_url"] = self.profile.text().strip()
        cfg["auto_discover"] = self.auto_discover.isChecked()
        cfg["poll"]["interval_minutes"] = self.interval.value()
        cfg["poll"]["notify_on_downloads"] = self.notify_downloads.isChecked()
        cfg["poll"]["notify_on_comments"] = self.notify_comments.isChecked()
        cfg["poll"]["notify_on_replies"] = self.notify_replies.isChecked()
        cfg["poll"]["charts_each_poll"] = self.charts_each_poll.isChecked()
        cfg["notifications"]["max_toasts"] = self.max_toasts.value()
        cfg["notifications"]["app_id"] = self.app_id.text().strip() or "ModDB Tracker"
        cfg["tray"]["close_to_tray"] = self.close_to_tray.isChecked()
        cfg["tray"]["start_minimized"] = self.start_minimized.isChecked()
        return cfg

    def _save(self) -> None:
        try:
            save_config(self.current_config(), CONFIG_FILE)
            QMessageBox.information(self, "Saved", "Settings saved to config.json")
            self.saved.emit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save failed", str(exc))

    def _open_config(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(CONFIG_FILE).resolve())))


# --------------------------------------------------------------------------
# main window
# --------------------------------------------------------------------------

class TrackerWindow(QMainWindow):
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
        self.resize(1180, 760)

        self._build_ui()
        self._wire_logging()
        self._build_tray()

        # auto-poll timer
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self._poll_now)
        self.auto_checkbox = QCheckBox("Auto-poll")
        self.auto_checkbox.toggled.connect(self._toggle_auto_poll)

        self.statusBar().addWidget(self.auto_checkbox)
        self.status_label = QLabel("")
        self.statusBar().addPermanentWidget(self.status_label)

        self.refresh_all()
        self.set_status("Ready. First run: click \"Poll now\" to fetch data.")

    # ---- ui construction ------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # toolbar
        toolbar = QHBoxLayout()
        self.poll_btn = QPushButton("Poll now")
        self.poll_btn.setObjectName("Primary")
        self.poll_btn.clicked.connect(self._poll_now)
        self.rescan_btn = QPushButton("Rescan profile")
        self.rescan_btn.clicked.connect(self._rescan)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_all)
        self.charts_btn = QPushButton("Regenerate charts")
        self.charts_btn.clicked.connect(self._regenerate_charts)
        toolbar.addWidget(self.poll_btn)
        toolbar.addWidget(self.rescan_btn)
        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.charts_btn)
        toolbar.addStretch(1)
        root.addLayout(toolbar)

        # sidebar + content
        body = QHBoxLayout()
        body.setSpacing(12)
        sidebar = QListWidget()
        sidebar.setFixedWidth(190)
        sidebar.setObjectName("Sidebar")
        self.nav = ["Dashboard", "Mods", "History", "Comments", "Events", "Settings", "Log"]
        for name in self.nav:
            sidebar.addItem(QListWidgetItem(name))
        sidebar.currentRowChanged.connect(self._nav_changed)
        body.addWidget(sidebar)

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
        self.mods.url_double_clicked.connect(self._open_url)
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)

        self.setCentralWidget(central)
        sidebar.setCurrentRow(0)

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
            # close button hides to tray instead of quitting
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
        self.mods.refresh(self.storage)
        self.history.refresh(self.storage)
        self.comments.refresh(self.storage)
        self.events.refresh(self.storage)
        self.dashboard.reload()
        self.settings.reload()

        member = self.storage.meta_get("member_name") or ""
        last = self.storage.meta_get("last_poll") or ""
        bits = [f"Member: {member}"] if member else ["Member: not set"]
        bits.append(f"Last poll: {last}" if last else "Never polled")
        self.status_label.setText("   |   ".join(bits))
        self._update_tray_tooltip(member, last)

    def _on_settings_saved(self) -> None:
        self.config = load_config(self.config_path)
        self.storage = Storage(self.config["paths"]["db"])
        self.dashboard._config = self.config
        self._restart_auto_timer()
        self.refresh_all()

    def _open_url(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    # ---- actions --------------------------------------------------------
    def _set_busy(self, busy: bool, label: str = "") -> None:
        self.poll_btn.setEnabled(not busy)
        self.rescan_btn.setEnabled(not busy)
        self.charts_btn.setEnabled(not busy)
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

    def closeEvent(self, event) -> None:  # noqa: N802
        self._stopping = True
        self.auto_timer.stop()
        if self.worker is not None and self.worker.isRunning():
            self.worker.wait(5000)
        self.storage.close()
        event.accept()


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
