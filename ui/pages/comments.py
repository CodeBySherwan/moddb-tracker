"""ui/pages/comments.py"""

from typing import Any, Dict, List, Optional
from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget
from storage import Storage
from ui.widgets import fill_table, make_table

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

