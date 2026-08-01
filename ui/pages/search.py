"""ui/pages/search.py"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from typing import Any, Dict, Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QHeaderView, QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
from ui.icons import _icon

class SearchResultsPage(QWidget):
    """Global search results grouped by category (mods / comments / events / history)."""

    open_url = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.title = QLabel("Search")
        self.title.setObjectName("PageTitle")
        layout.addWidget(self.title)
        self.hint = QLabel("Type in the search bar to look across mods, comments, events and history.")
        self.hint.setObjectName("Hint")
        layout.addWidget(self.hint)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Type", "Match", "Detail"])
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.itemDoubleClicked.connect(self._open_item)
        layout.addWidget(self.tree, 1)

    def apply_filter(self, text: str) -> None:
        needle = (text or "").strip()
        storage = getattr(self, "_storage", None)
        self.tree.clear()
        if not needle:
            self.hint.setText("Type at least 2 characters in the search bar to search everything.")
            return
        if len(needle) < 2 or storage is None:
            return
        results = storage.search(needle)
        self.hint.setText(f"Results for \u201c{needle}\u201d")
        total = 0
        for group, rows, icon_name in (
            ("Mods", results["mods"], "package"),
            ("Comments", results["comments"], "chat"),
            ("Events", results["events"], "bell"),
            ("History", results["history"], "trend"),
        ):
            if not rows:
                continue
            section = QTreeWidgetItem([f"{group} ({len(rows)})", "", ""])
            section.setIcon(0, QIcon(_icon(icon_name, "#94A3B8", 16)))
            section.setExpanded(True)
            for r in rows:
                child = self._row_item(group, r)
                if child is not None:
                    section.addChild(child)
                    total += 1
            self.tree.addTopLevelItem(section)
        if total == 0:
            self.tree.addTopLevelItem(QTreeWidgetItem([f"No matches for \u201c{needle}\u201d.", "", ""]))
        self.tree.expandAll()

    def _row_item(self, group: str, row: Dict[str, Any]) -> Optional[QTreeWidgetItem]:
        url = str(row.get("url") or row.get("mod_url") or "")
        if group == "Mods":
            item = QTreeWidgetItem(["Mod", row["name"], row.get("content_type", "mod")])
        elif group == "Comments":
            content = " ".join(str(row.get("content") or "").split())
            item = QTreeWidgetItem(["Comment", f"{row['author']}: {content[:120]}", f"{row.get('mod_name', '')} · {row.get('posted_at', '')}"])
        elif group == "Events":
            item = QTreeWidgetItem(["Event", str(row.get("message", ""))[:160], f"{row.get('mod_name') or ''} · {row.get('created_at', '')}"])
        elif group == "History":
            item = QTreeWidgetItem(["History", f"{row.get('mod_name', '')} — {int(row.get('downloads_total') or 0):,} downloads", row.get("fetched_at", "")])
        else:
            return None
        if url:
            item.setData(0, Qt.ItemDataRole.UserRole, url)
        return item

    def _open_item(self, item: QTreeWidgetItem, _column: int) -> None:
        url = item.data(0, Qt.ItemDataRole.UserRole)
        if url:
            self.open_url.emit(str(url))

