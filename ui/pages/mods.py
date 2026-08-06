"""ui/pages/mods.py"""

import datetime
from typing import Any, Dict, List, Optional
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget
from tracker import CONFIG_FILE, save_config
from storage import Storage
from ui.widgets import FlowLayout, ModCard

class ModsPage(QWidget):
    open_requested = pyqtSignal(str)
    refresh_requested = pyqtSignal(int)
    favorite_toggled = pyqtSignal(str, bool)
    remove_requested = pyqtSignal(str)
    export_requested = pyqtSignal()

    def __init__(self, config: Dict[str, Any], config_path: str = CONFIG_FILE, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config
        self._config_path = config_path
        self._cards: List[ModCard] = []
        self._filter = str(config.get("ui", {}).get("mods_filter", ""))
        self._sort = int(config.get("ui", {}).get("mods_sort", 0))
        self._prefs_timer = QTimer(self)
        self._prefs_timer.setSingleShot(True)
        self._prefs_timer.setInterval(400)
        self._prefs_timer.timeout.connect(self._save_ui_prefs)

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
        if self._filter:
            self.search.setText(self._filter)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Sort: Downloads", "Sort: Today", "Sort: 7-day growth", "Sort: Name", "Sort: Favorites first"])
        self.sort_combo.setCurrentIndex(self._sort)
        self.sort_combo.currentIndexChanged.connect(self._sort_changed)
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

    def _sort_changed(self, index: int) -> None:
        self._sort = index
        self._rebuild()
        self._save_ui_prefs()

    def _save_ui_prefs(self) -> None:
        try:
            self._config.setdefault("ui", {})["mods_sort"] = self._sort
            self._config["ui"]["mods_filter"] = self._filter
            save_config(self._config, self._config_path)
        except Exception:  # noqa: BLE001
            pass

    def refresh(self, storage: Storage) -> None:
        self._rebuild(storage)

    def _rebuild(self, storage: Optional[Storage] = None) -> None:
        if storage is not None:
            self._storage = storage
        storage = getattr(self, "_storage", None)
        if storage is None:
            return

        totals_rows = storage.totals_per_mod()
        totals = {int(t["id"]): t for t in totals_rows}
        mods = {int(m["id"]): m for m in storage.get_mods(active_only=True)}

        # per-mod deltas (7-day growth) from snapshots
        deltas: Dict[int, int] = {}
        updated_at: Dict[int, str] = {}
        snaps = storage.snapshots_for_all([int(m["id"]) for m in mods.values()])
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
        for mod_id in sorted(mods):
            meta = dict(mods[mod_id])
            if mod_id in totals:
                t = totals[mod_id]
            else:
                t = {
                    "id": mod_id, "name": meta.get("name"), "name_id": meta.get("name_id"),
                    "url": meta.get("url"), "downloads_total": None, "downloads_today": None,
                    "visits": None, "visits_today": None, "rank": None, "rank_total": None,
                    "watchers": None, "rating": None, "files": None, "comments": 0,
                    "replies": 0, "thread_replies": 0, "favorite": meta.get("favorite", 0),
                }
            card = ModCard()
            card.set_data(t, meta, delta_7d=deltas.get(mod_id, 0),
                          updated=updated_at.get(mod_id, ""))
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
        if not has_any:
            auto = bool(self._config.get("auto_discover"))
            never_polled = not storage.meta_get("last_poll")
            if auto and never_polled:
                self.placeholder.setText(
                    "Nothing tracked yet.\n\nAuto-discovery is on. Click \u201cPoll now\u201d or wait for "
                    "the next scheduled poll to find your mods automatically."
                )
            elif auto:
                self.placeholder.setText(
                    "Nothing tracked yet.\n\nAuto-discovery is on but hasn\u2019t found anything yet \u2014 "
                    "check your profile_url in Configuration, or add mods under Manual mods."
                )
            else:
                self.placeholder.setText(
                    "Nothing tracked yet.\n\nAdd mods in Configuration \u2192 Manual mods, or click "
                    "\u201cRescan profile\u201d to auto-discover your content."
                )

    def _apply_sort(self) -> None:
        if self._sort == 0:
            key = _card_downloads
        elif self._sort == 1:
            key = _card_today
        elif self._sort == 2:
            key = _card_growth
        elif self._sort == 3:
            key = lambda c: c._full_name.lower()
        else:
            key = lambda c: (not c._favorite, _card_downloads(c))
        self._cards.sort(key=key, reverse=(self._sort in (0, 1, 2, 4)))
        while self.flow.count():
            self.flow.takeAt(0)
        for card in self._cards:
            self.flow.add_card(card)

    def apply_filter(self, text: str) -> None:
        self._filter = text
        self._apply_filter()
        self._prefs_timer.start()
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
    return card.downloads_total


def _card_today(card: ModCard) -> int:
    return card.downloads_today


def _card_growth(card: ModCard) -> int:
    return card.growth_7d

