"""ui/pages/compare.py"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from typing import Any, Dict, List, Optional, Tuple
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QScrollArea, QTableWidgetItem, QVBoxLayout, QWidget
from pyqtgraph.exporters import ImageExporter
import analytics
from tracker import CONFIG_FILE
from storage import Storage
from ui.theme import ACCENT, ERROR, GRAY, SUCCESS
from ui.widgets import PlotCard, make_table

class ComparePage(QWidget):
    """Head-to-head comparison of two tracked mods (Phase 3)."""

    COLOR_A = ACCENT
    COLOR_B = SUCCESS

    def __init__(self, config: Dict[str, Any], config_path: str = CONFIG_FILE, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config
        self._config_path = config_path
        self._storage: Optional[Storage] = None
        self._mods: List[Dict[str, Any]] = []
        self._summary_a: Optional[Dict[str, Any]] = None
        self._summary_b: Optional[Dict[str, Any]] = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)

        title = QLabel("Compare")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        hint = QLabel("Compare two mods head-to-head \u2014 totals, growth and the daily advantage.")
        hint.setObjectName("Hint")
        layout.addWidget(hint)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.combo_a = QComboBox()
        self.combo_a.setMinimumWidth(230)
        self.combo_a.currentIndexChanged.connect(self._on_combo_changed)
        self.combo_b = QComboBox()
        self.combo_b.setMinimumWidth(230)
        self.combo_b.currentIndexChanged.connect(self._on_combo_changed)
        controls.addWidget(QLabel("Mod A:"))
        controls.addWidget(self.combo_a)
        controls.addWidget(QLabel("Mod B:"))
        controls.addWidget(self.combo_b)
        controls.addWidget(QLabel("Range:"))
        self.days_combo = QComboBox()
        for n in (30, 60, 90):
            self.days_combo.addItem(f"Last {n} days", n)
        self.days_combo.setCurrentIndex(1)
        self.days_combo.currentIndexChanged.connect(self._days_changed)
        controls.addWidget(self.days_combo)
        controls.addStretch(1)
        self.export_btn = QPushButton("Export charts\u2026")
        self.export_btn.clicked.connect(self._export_charts)
        controls.addWidget(self.export_btn)
        layout.addLayout(controls)

        self.table = make_table(["Metric", "Mod A", "Mod B"], selectable=False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(330)
        self.table.setMaximumHeight(360)
        layout.addWidget(self.table)

        self.grid_host = QWidget()
        grid = QGridLayout(self.grid_host)
        grid.setSpacing(12)
        self.plot_cum = PlotCard("Cumulative downloads", f"blue = Mod A   \u00b7   green = Mod B")
        self.plot_daily = PlotCard("Downloads per day", "Daily gain, both mods")
        self.plot_diff = PlotCard("Daily advantage", "green: A ahead   \u00b7   red: B ahead")
        grid.addWidget(self.plot_cum, 0, 0)
        grid.addWidget(self.plot_daily, 0, 1)
        grid.addWidget(self.plot_diff, 1, 0, 1, 2)
        layout.addWidget(self.grid_host, 1)

        self.placeholder = QLabel("Track at least two mods to compare them here.")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setObjectName("Hint")
        self.placeholder.setMinimumHeight(160)
        layout.addWidget(self.placeholder, 1)

        self.scroll.setWidget(content)
        outer.addWidget(self.scroll)

    # ---- refresh --------------------------------------------------------
    def refresh(self, storage: Storage) -> None:
        self._storage = storage
        self._mods = [dict(m) for m in storage.get_mods(active_only=True)]
        current_a = self.combo_a.currentData()
        current_b = self.combo_b.currentData()
        self.combo_a.blockSignals(True)
        self.combo_b.blockSignals(True)
        self.combo_a.clear()
        self.combo_b.clear()
        for m in self._mods:
            self.combo_a.addItem(m["name"], int(m["id"]))
            self.combo_b.addItem(m["name"], int(m["id"]))
        if len(self._mods) >= 2:
            if current_a is not None and self.combo_a.findData(current_a) >= 0:
                self.combo_a.setCurrentIndex(self.combo_a.findData(current_a))
            elif len(self._mods) >= 2:
                self.combo_a.setCurrentIndex(0)
            if current_b is not None and self.combo_b.findData(current_b) >= 0:
                self.combo_b.setCurrentIndex(self.combo_b.findData(current_b))
            elif len(self._mods) >= 2:
                self.combo_b.setCurrentIndex(1)
        self.combo_a.blockSignals(False)
        self.combo_b.blockSignals(False)
        self._update()

    def _days_changed(self) -> None:
        self._update()

    def _on_combo_changed(self) -> None:
        if len(self._mods) >= 2 and self.combo_a.currentData() == self.combo_b.currentData():
            # auto-move B to the other mod so they can never be identical
            ids = [int(m["id"]) for m in self._mods]
            a = self.combo_a.currentData()
            self.combo_b.blockSignals(True)
            for i, mid in enumerate(ids):
                if mid != a:
                    self.combo_b.setCurrentIndex(i)
                    break
            self.combo_b.blockSignals(False)
        self._update()

    def _update(self) -> None:
        storage = self._storage
        has = bool(self._mods)
        ready = has and len(self._mods) >= 2 and storage is not None
        self.placeholder.setVisible(not ready)
        self.table.setVisible(ready)
        self.grid_host.setVisible(ready)
        for card in (self.plot_cum, self.plot_daily, self.plot_diff):
            card.clear_chart()
        self.table.setRowCount(0)
        if not ready:
            for combo in (self.combo_a, self.combo_b, self.days_combo):
                combo.setEnabled(has)
            self.export_btn.setEnabled(False)
            self.placeholder.setText("Track at least two mods to compare them here." if not has else
                                     "Only one mod tracked. Add a second mod to compare them here.")
            return

        days = int(self.days_combo.currentData() or 60)
        mid_a = int(self.combo_a.currentData())
        mid_b = int(self.combo_b.currentData())
        self._summary_a = analytics.mod_summary(storage, mid_a, days)
        self._summary_b = analytics.mod_summary(storage, mid_b, days)
        a, b = self._summary_a, self._summary_b

        names = {int(m["id"]): m["name"] for m in self._mods}
        self._names = (names.get(mid_a, "A"), names.get(mid_b, "B"))
        name_a, name_b = self._names

        self._fill_table(a, b)
        self._draw_charts(a, b, days)

    # ---- stats table ----------------------------------------------------
    def _fill_table(self, a: Dict[str, Any], b: Dict[str, Any]) -> None:
        def best_day(s: Dict[str, Any]) -> str:
            return f"{s['best_day']['label']} (+{s['best_day']['value']:,})" if s["best_day"] else "—"

        def best_week(s: Dict[str, Any]) -> str:
            return f"{s['best_week']['label']} (+{s['best_week']['value']:,})" if s["best_week"] else "—"

        def milestone_count(s: Dict[str, Any]) -> int:
            return len([m for m in s["milestones"] if m["threshold"] >= 100_000])

        rows: List[Tuple[str, str, str, int, int]] = []  # metric, a_text, b_text, a_win, b_win
        rows.append(("Total downloads", f"{a['total']:,}", f"{b['total']:,}", a["total"], b["total"]))
        rows.append(("Last 7 days", f"+{a['delta_7d']:,}", f"+{b['delta_7d']:,}", a["delta_7d"], b["delta_7d"]))
        rows.append(("Last 30 days", f"+{a['delta_30d']:,}", f"+{b['delta_30d']:,}", a["delta_30d"], b["delta_30d"]))
        rows.append(("Avg / day", f"{a['avg_per_day']}", f"{b['avg_per_day']}", a["avg_per_day"], b["avg_per_day"]))
        rows.append(("Growth (30d)", f"{a['growth_pct']}%", f"{b['growth_pct']}%", a["growth_pct"], b["growth_pct"]))
        rows.append(("Best day", best_day(a), best_day(b), a["best_day"]["value"] if a["best_day"] else 0,
                     b["best_day"]["value"] if b["best_day"] else 0))
        rows.append(("Best week", best_week(a), best_week(b), a["best_week"]["value"] if a["best_week"] else 0,
                     b["best_week"]["value"] if b["best_week"] else 0))
        rows.append(("Next week (est.)", f"{a['next_week_estimate']:,}" if a["next_week_estimate"] else "—",
                     f"{b['next_week_estimate']:,}" if b["next_week_estimate"] else "—",
                     a["next_week_estimate"] or 0, b["next_week_estimate"] or 0))
        rows.append(("Milestones", f"{milestone_count(a)}", f"{milestone_count(b)}",
                     milestone_count(a), milestone_count(b)))
        rows.append(("First seen", str(a["first_seen"] or "—"), str(b["first_seen"] or "—"), 0, 0))

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for r, (metric, ta, tb, va, vb) in enumerate(rows):
            m_item = QTableWidgetItem(metric)
            m_item.setForeground(QColor(GRAY))
            a_item = QTableWidgetItem(ta)
            b_item = QTableWidgetItem(tb)
            if va > vb:
                a_item.setForeground(QColor(SUCCESS))
            elif va < vb:
                b_item.setForeground(QColor(SUCCESS))
            self.table.setItem(r, 0, m_item)
            self.table.setItem(r, 1, a_item)
            self.table.setItem(r, 2, b_item)
        self.table.resizeColumnsToContents()

    # ---- charts ---------------------------------------------------------
    def _draw_charts(self, a: Dict[str, Any], b: Dict[str, Any], days: int) -> None:
        name_a, name_b = self._names
        aligned = analytics.aligned_totals(a["series"], b["series"], days)

        self.plot_cum.set_ylabel("Total downloads")
        dates = [t[0] for t in aligned]
        self.plot_cum.add_line(dates, [t[1] for t in aligned], self.COLOR_A, width=2, name=name_a)
        self.plot_cum.add_line(dates, [t[2] for t in aligned], self.COLOR_B, width=2, name=name_b)
        self.plot_cum.info.setText(f"{name_a} ({self.COLOR_A})   vs   {name_b} ({self.COLOR_B})")

        self.plot_daily.set_ylabel("Downloads")
        if a["deltas"]:
            self.plot_daily.add_bars(*zip(*a["deltas"]), self.COLOR_A, name=name_a, alpha=110)
        if b["deltas"]:
            self.plot_daily.add_bars(*zip(*b["deltas"]), self.COLOR_B, name=name_b, alpha=110)
        self.plot_daily.info.setText(f"{name_a} (blue)   vs   {name_b} (green)")

        self.plot_diff.set_ylabel("Downloads ahead")
        ahead_dates, ahead_vals = [], []
        behind_dates, behind_vals = [], []
        for day, va, vb in aligned:
            diff = va - vb
            if diff >= 0:
                ahead_dates.append(day)
                ahead_vals.append(diff)
            else:
                behind_dates.append(day)
                behind_vals.append(-diff)
        if ahead_dates:
            self.plot_diff.add_bars(ahead_dates, ahead_vals, SUCCESS, name=f"{name_a} ahead", alpha=170)
        if behind_dates:
            self.plot_diff.add_bars(behind_dates, behind_vals, ERROR, name=f"{name_b} ahead", alpha=170)

    # ---- export ---------------------------------------------------------
    def _export_charts(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, "Choose a folder for chart PNGs")
        if not dir_path:
            return
        try:
            written = []
            for slug, card in (("cumulative", self.plot_cum), ("daily", self.plot_daily), ("diff", self.plot_diff)):
                path = Path(dir_path) / f"compare_{slug}.png"
                exporter = ImageExporter(card.plot.getPlotItem())
                exporter.parameters()["width"] = 1200
                exporter.export(str(path))
                written.append(path.name)
            QMessageBox.information(self, "Charts exported", "Saved:\n" + "\n".join(written))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Export failed", str(exc))

