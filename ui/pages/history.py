"""ui/pages/history.py"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from typing import Any, List, Optional
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTabWidget, QVBoxLayout, QWidget
import analytics
from storage import Storage
from ui.theme import ACCENT, SUCCESS
from ui.widgets import PlotCard, fill_table, make_table

class HistoryPage(QWidget):
    """Backfilled per-day history from the ModDB stats page + poll snapshots."""

    backfill_requested = pyqtSignal(int)
    backfill_all_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        title = QLabel("History")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        hint = QLabel(
            "\u201cModDB stats history\u201d holds the per-day counters backfilled from ModDB's public "
            "stats page \u2014 a full daily visitor count since release. \u201cPoll snapshots\u201d are the "
            "rows collected by your polls."
        )
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Item:"))
        self.mod_combo = QComboBox()
        self.mod_combo.currentIndexChanged.connect(lambda _: self._populate())
        controls.addWidget(self.mod_combo, 1)
        self.backfill_btn = QPushButton("Backfill this mod")
        self.backfill_btn.setToolTip("Fetch the full per-day history from the ModDB stats page")
        self.backfill_btn.clicked.connect(self._request_backfill)
        controls.addWidget(self.backfill_btn)
        self.backfill_all_btn = QPushButton("Backfill all mods")
        self.backfill_all_btn.setToolTip("Fetch the stats page for every tracked mod")
        self.backfill_all_btn.clicked.connect(self.backfill_all_requested)
        controls.addWidget(self.backfill_all_btn)
        layout.addLayout(controls)

        self.coverage = QLabel("")
        self.coverage.setObjectName("Hint")
        self.coverage.setWordWrap(True)
        layout.addWidget(self.coverage)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        stats_tab = QWidget()
        v = QVBoxLayout(stats_tab)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        self.plot_full = PlotCard(
            "Daily counts from ModDB", "Cumulative visits and downloads over the backfilled history"
        )
        self.plot_full.set_ylabel("count")
        v.addWidget(self.plot_full)
        self.stats_table = make_table(
            ["Day", "Visits", "Downloads", "Videos", "Images", "Articles"]
        )
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        v.addWidget(self.stats_table, 1)
        self.tabs.addTab(stats_tab, "ModDB stats history")

        snap_tab = QWidget()
        v2 = QVBoxLayout(snap_tab)
        v2.setContentsMargins(0, 0, 0, 0)
        self.table = make_table(
            ["Fetched", "Downloads", "Today", "Delta", "Visits", "Visits today", "Rank", "Watchers"]
        )
        v2.addWidget(self.table, 1)
        self.tabs.addTab(snap_tab, "Poll snapshots")

        layout.addWidget(self.tabs, 1)
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

    def _request_backfill(self) -> None:
        mod_id = self.mod_combo.currentData()
        if mod_id is not None:
            self.backfill_requested.emit(mod_id)

    def _populate(self) -> None:
        if self._storage is None:
            return
        mod_id = self.mod_combo.currentData()
        self._populate_stats(mod_id)
        self._populate_snapshots(mod_id)

    def _populate_stats(self, mod_id: Optional[int]) -> None:
        self.plot_full.clear_chart()
        if mod_id is None:
            fill_table(self.stats_table, [])
            self.coverage.setText("")
            return

        rows = analytics.stats_history_series(self._storage, mod_id)
        fill_table(
            self.stats_table,
            [[r["day"], r["visits"], r["downloads"], r["videos"], r["images"], r["articles"]]
             for r in rows],
        )

        coverage = self._storage.stats_history_coverage(mod_id)
        if not coverage["days"]:
            self.coverage.setText(
                "No backfilled history yet \u2014 click \u201cBackfill this mod\u201d to fetch the "
                "full daily history from ModDB."
            )
            return

        counts = coverage["counts"]
        self.coverage.setText(
            f"Backfilled: {coverage['days']:,} day(s) ({coverage['first']} \u2192 {coverage['last']}). "
            f"Daily counts \u2014 visits {counts['visits']:,} \u00b7 downloads {counts['downloads']:,} \u00b7 "
            f"videos {counts['videos']:,} \u00b7 images {counts['images']:,} \u00b7 articles {counts['articles']:,}"
        )

        visits_cum = analytics.stats_history_cumulative(self._storage, mod_id, "visits")
        downloads_cum = analytics.stats_history_cumulative(self._storage, mod_id, "downloads")
        if visits_cum:
            self.plot_full.add_line(
                [d for d, _ in visits_cum], [v for _, v in visits_cum],
                SUCCESS, width=2, fill=True, name="Visits",
            )
        if downloads_cum:
            self.plot_full.add_line(
                [d for d, _ in downloads_cum], [v for _, v in downloads_cum],
                ACCENT, width=2, name="Downloads",
            )

    def _populate_snapshots(self, mod_id: Optional[int]) -> None:
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

