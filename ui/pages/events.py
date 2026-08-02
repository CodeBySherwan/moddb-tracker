"""ui/pages/events.py"""

from typing import Any, Dict, List, Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon
from PyQt6.QtWidgets import QApplication, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu, QPushButton, QTableWidgetItem, QVBoxLayout, QWidget
from storage import Storage
from ui.theme import ACCENT, GRAY, SUCCESS, TEXT, WARNING
from ui.icons import _icon
from ui.widgets import make_table

class EventsPage(QWidget):
    """Notification center: unseen highlighting, kind filter, mark-as-read, open on ModDB."""

    open_url = pyqtSignal(str)
    events_read = pyqtSignal()

    KIND_LABELS = {"download": "Downloads", "comment": "Comments", "reply": "Replies"}
    KIND_STYLE = {"download": ("download", SUCCESS), "comment": ("chat", ACCENT), "reply": ("reply", WARNING)}

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._filter = ""
        self._kind = ""
        self._rows: List[Dict[str, Any]] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        title = QLabel("Notifications")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        hint = QLabel("Download and comment events detected by polls. Double-click a row to open it on ModDB.")
        hint.setObjectName("Hint")
        layout.addWidget(hint)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText("Search events\u2026")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(240)
        self.search.textChanged.connect(lambda _: self._apply_filter())
        toolbar.addWidget(self.search)
        self.kind_combo = QComboBox()
        self.kind_combo.addItem("All kinds", "")
        self.kind_combo.addItem("Downloads", "download")
        self.kind_combo.addItem("Comments", "comment")
        self.kind_combo.addItem("Replies", "reply")
        self.kind_combo.currentIndexChanged.connect(lambda _: self._apply_filter())
        toolbar.addWidget(self.kind_combo)
        toolbar.addStretch(1)
        self.mark_read_btn = QPushButton("Mark all read")
        self.mark_read_btn.clicked.connect(self.mark_all_seen)
        toolbar.addWidget(self.mark_read_btn)
        layout.addLayout(toolbar)

        self.table = make_table(["Time", "Kind", "Mod", "Message"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.itemDoubleClicked.connect(lambda _: self._open_selected())
        layout.addWidget(self.table, 1)
        self.placeholder = QLabel("No events yet. Run a poll to start recording activity.")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setObjectName("Hint")
        self.placeholder.setMinimumHeight(120)
        layout.addWidget(self.placeholder)

    def refresh(self, storage: Storage) -> None:
        self._storage = storage
        rows: List[Dict[str, Any]] = []
        for e in storage.recent_events(200):
            rows.append({
                "id": e["id"],
                "created_at": e["created_at"],
                "kind": e["kind"],
                "mod_name": e["mod_name"] or "-",
                "message": e["message"],
                "url": e["url"] or "",
                "seen": bool(e["seen"]),
            })
        self._rows = rows
        self._apply_filter()

    def mark_all_seen(self) -> None:
        storage = getattr(self, "_storage", None)
        if storage is not None:
            storage.mark_events_seen()
        for r in self._rows:
            r["seen"] = True
        self._apply_filter()
        self.events_read.emit()

    def apply_filter(self, text: str) -> None:
        self.search.setText(text)
        self._apply_filter()

    def _mark_all_read(self) -> None:
        self.mark_all_seen()

    def _open_selected(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self._displayed):
            url = self._displayed[row].get("url")
            if url:
                self.open_url.emit(url)

    def _context_menu(self, pos) -> None:
        row = self.table.rowAt(pos.y())
        if row < 0 or row >= len(self._displayed):
            return
        entry = self._displayed[row]
        menu = QMenu(self)
        if entry.get("url"):
            open_act = QAction("Open on ModDB", self)
            open_act.triggered.connect(lambda: self.open_url.emit(entry["url"]))
            menu.addAction(open_act)
            copy_act = QAction("Copy URL", self)
            copy_act.triggered.connect(lambda: QApplication.clipboard().setText(entry["url"]))
            menu.addAction(copy_act)
            menu.addSeparator()
        mark_act = QAction("Mark all read", self)
        mark_act.triggered.connect(self._mark_all_read)
        menu.addAction(mark_act)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _apply_filter(self) -> None:
        needle = self.search.text().strip().lower()
        self._kind = self.kind_combo.currentData() or ""
        out = []
        for r in self._rows:
            if self._kind and r["kind"] != self._kind:
                continue
            if needle and needle not in f"{r['kind']} {r['mod_name']} {r['message']}".lower():
                continue
            out.append(r)
        self._displayed = out

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(out))
        for r, entry in enumerate(out):
            icon_name, color = self.KIND_STYLE.get(entry["kind"], ("dot", GRAY))
            kind_label = self.KIND_LABELS.get(entry["kind"], entry["kind"].title())
            cells = [entry["created_at"], kind_label, entry["mod_name"], entry["message"]]
            for c, value in enumerate(cells):
                item = QTableWidgetItem(str(value))
                if c == 1:
                    item.setIcon(QIcon(_icon(icon_name, color, 16)))
                if not entry["seen"]:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setForeground(QColor(TEXT))
                if c == 0:
                    item.setData(Qt.ItemDataRole.UserRole, entry["created_at"])
                self.table.setItem(r, c, item)
        self.table.resizeColumnsToContents()

        self.placeholder.setVisible(not self._rows)
        self.table.setVisible(bool(self._rows))

