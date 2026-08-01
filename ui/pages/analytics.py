"""ui/pages/analytics.py"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
import datetime
from typing import Any, Dict, List, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget
from pyqtgraph.exporters import ImageExporter
import analytics
from tracker import CONFIG_FILE, save_config
from storage import Storage
from ui.theme import ACCENT, GRAY, LINE_COLORS, SUCCESS, WARNING
from ui.widgets import PlotCard, StatCard

class AnalyticsPage(QWidget):
    """Interactive downloads analytics: pyqtgraph charts with zoom, hover, export."""


    def __init__(self, config: Dict[str, Any], config_path: str = CONFIG_FILE, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config
        self._config_path = config_path
        self._storage: Optional[Storage] = None
        self._summaries: List[Dict[str, Any]] = []

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

        title = QLabel("Analytics")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        hint = QLabel("Interactive downloads analytics \u2014 hover a chart for values, drag to zoom.")
        hint.setObjectName("Hint")
        layout.addWidget(hint)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        controls.addWidget(QLabel("Mod:"))
        self.mod_combo = QComboBox()
        self.mod_combo.setMinimumWidth(240)
        self.mod_combo.currentIndexChanged.connect(self._mod_changed)
        controls.addWidget(self.mod_combo)
        controls.addWidget(QLabel("Range:"))
        self.days_combo = QComboBox()
        for n in (30, 60, 90):
            self.days_combo.addItem(f"Last {n} days", n)
        self.days_combo.setCurrentIndex(self._default_days_index())
        self.days_combo.currentIndexChanged.connect(self._days_changed)
        controls.addWidget(self.days_combo)
        controls.addStretch(1)
        self.export_btn = QPushButton("Export charts\u2026")
        self.export_btn.clicked.connect(self._export_charts)
        controls.addWidget(self.export_btn)
        layout.addLayout(controls)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.stat_total = StatCard("Total downloads")
        self.stat_7d = StatCard("Last 7 days")
        self.stat_30d = StatCard("Last 30 days")
        self.stat_next = StatCard("Next 7 days (est.)")
        for c in (self.stat_total, self.stat_7d, self.stat_30d, self.stat_next):
            cards.addWidget(c, 1)
        layout.addLayout(cards)

        self.highlights = QFrame()
        self.highlights.setObjectName("Panel")
        self.highlights_label = QLabel("")
        self.highlights_label.setWordWrap(True)
        hl = QHBoxLayout(self.highlights)
        hl.setContentsMargins(14, 10, 14, 10)
        hl.addWidget(self.highlights_label)
        layout.addWidget(self.highlights)

        self.grid_host = QWidget()
        grid = QGridLayout(self.grid_host)
        grid.setSpacing(12)
        self.plot_daily = PlotCard("Downloads per day", "Bars: daily gain   \u00b7   line: 7-day average")
        self.plot_cum = PlotCard("Cumulative downloads", "Total downloads over time")
        self.plot_weekly = PlotCard("Weekly downloads", "Downloads gained per ISO week")
        grid.addWidget(self.plot_daily, 0, 0)
        grid.addWidget(self.plot_cum, 0, 1)
        grid.addWidget(self.plot_weekly, 1, 0, 1, 2)
        layout.addWidget(self.grid_host, 1)

        self.placeholder = QLabel("No data yet. Run a poll to start collecting download history.")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setObjectName("Hint")
        self.placeholder.setMinimumHeight(160)
        layout.addWidget(self.placeholder, 1)

        self.scroll.setWidget(content)
        outer.addWidget(self.scroll)

    def _default_days_index(self) -> int:
        days = int(self._config.get("ui", {}).get("analytics_days", 60))
        idx = self.days_combo.findData(days)
        return idx if idx >= 0 else 1

    # ---- refresh --------------------------------------------------------
    def refresh(self, storage: Storage) -> None:
        self._storage = storage
        days = int(self.days_combo.currentData() or 60)
        self._summaries = analytics.all_mods_summary(storage, days)
        current = self.mod_combo.currentData()
        self.mod_combo.blockSignals(True)
        self.mod_combo.clear()
        self.mod_combo.addItem("All tracked mods", None)
        for s in self._summaries:
            self.mod_combo.addItem(s["name"], s["mod_id"])
        if current is not None:
            idx = self.mod_combo.findData(current)
            if idx >= 0:
                self.mod_combo.setCurrentIndex(idx)
        self.mod_combo.blockSignals(False)
        self._update()

    def _days_changed(self) -> None:
        try:
            self._config.setdefault("ui", {})["analytics_days"] = int(self.days_combo.currentData() or 60)
            save_config(self._config, self._config_path)
        except Exception:  # noqa: BLE001
            pass
        if self._storage is not None:
            self.refresh(self._storage)

    def _mod_changed(self) -> None:
        self._update()

    # ---- rendering ------------------------------------------------------
    def _update(self) -> None:
        has = bool(self._summaries)
        self.placeholder.setVisible(not has)
        self.grid_host.setVisible(has)
        self.highlights.setVisible(has)
        for card in (self.plot_daily, self.plot_cum, self.plot_weekly):
            card.clear_chart()
        if not has:
            for s in (self.stat_total, self.stat_7d, self.stat_30d, self.stat_next):
                s.set_text("—")
            return

        sel = self.mod_combo.currentData()
        if sel is None:
            self._update_all()
        else:
            self._update_mod(sel)

    def _fill_cards(self, total: int, d7: int, d30: int, nxt: Optional[int]) -> None:
        self.stat_total.set_value(total, f"last 30 days: +{d30:,}", SUCCESS if d30 else GRAY)
        self.stat_7d.set_text(f"{d7:,}", "last 7 days", SUCCESS)
        self.stat_30d.set_text(f"{d30:,}", "last 30 days", SUCCESS)
        if nxt:
            self.stat_next.set_text(f"{nxt:,}", "linear projection", ACCENT)
        else:
            self.stat_next.set_text("—", "not enough data", GRAY)

    def _highlights_line(self, parts: List[str]) -> None:
        self.highlights_label.setText("  \u00b7  ".join(parts))
        self.highlights_label.setStyleSheet(f"color: {GRAY}; font-size: 12px;")

    def _update_all(self) -> None:
        agg = analytics.aggregate_summary(self._summaries)
        self._fill_cards(agg["total"], agg["delta_7d"], agg["delta_30d"], agg["next_week"])

        top = self._summaries[0]
        fastest = max(self._summaries, key=lambda s: s["delta_7d"]) if self._summaries else None
        ranked = ", ".join(f"{i + 1}. {s['name']} ({s['total']:,})" for i, s in enumerate(self._summaries[:3]))
        parts = [f"{agg['count']} tracked mods",
                 f"top: {top['name']} ({top['total']:,})",
                 f"fastest 7d: {fastest['name']} (+{fastest['delta_7d']:,})" if fastest else None,
                 f"ranking: {ranked}"]
        self._highlights_line([p for p in parts if p])

        today = datetime.date.today()
        days = int(self.days_combo.currentData() or 60)
        start = today - datetime.timedelta(days=days - 1)

        # daily deltas summed across mods
        agg_daily: Dict[datetime.date, int] = {}
        for s in self._summaries:
            for d, v in s["deltas"]:
                agg_daily[d] = agg_daily.get(d, 0) + v
        dailies = sorted(agg_daily.items())
        self.plot_daily.set_ylabel("Downloads")
        if dailies:
            self.plot_daily.add_bars(*zip(*dailies), ACCENT)
            ma = analytics.moving_average(dailies, 7)
            self.plot_daily.add_line(*zip(*ma), "#38BDF8", width=2)

        # cumulative per mod, aligned to the same window
        for i, s in enumerate(self._summaries):
            series = [p for p in s["series"] if p[0] >= start]
            totals = analytics.daily_totals_range(series, days)
            color = LINE_COLORS[i % len(LINE_COLORS)]
            self.plot_cum.add_line(*zip(*totals), color, width=2)
        self.plot_cum.set_ylabel("Total downloads")

        # weekly totals across mods
        weeks: Dict[datetime.date, int] = {}
        for s in self._summaries:
            for d, v in s["weeks"]:
                weeks[d] = weeks.get(d, 0) + v
        wk = sorted(weeks.items())
        self.plot_weekly.set_ylabel("Downloads")
        if wk:
            self.plot_weekly.add_bars(*zip(*wk), SUCCESS)

    def _update_mod(self, mod_id: int) -> None:
        s = next((x for x in self._summaries if x["mod_id"] == mod_id), None)
        if s is None:
            return
        self._fill_cards(s["total"], s["delta_7d"], s["delta_30d"], s["next_week_estimate"])

        parts = [f"first seen: {s['first_seen']}",
                 f"best day: {s['best_day']['label']} (+{s['best_day']['value']:,})" if s["best_day"] else None,
                 f"best week: {s['best_week']['label']} (+{s['best_week']['value']:,})" if s["best_week"] else None,
                 f"avg/day: {s['avg_per_day']}"]
        if s["milestones"]:
            ms = ", ".join(f"{m['threshold']:,} ({m['date']})" for m in s["milestones"])
            parts.append(f"milestones: {ms}")
        else:
            parts.append("milestones: none reached in range")
        self._highlights_line([p for p in parts if p])

        self.plot_daily.set_ylabel("Downloads")
        if s["deltas"]:
            self.plot_daily.add_bars(*zip(*s["deltas"]), ACCENT)
            self.plot_daily.add_line(*zip(*s["ma7"]), "#38BDF8", width=2)

        totals = analytics.daily_totals_range(s["series"], s["days"])
        self.plot_cum.set_ylabel("Total downloads")
        self.plot_cum.add_line(*zip(*totals), ACCENT, width=2, fill=True)
        for m in s["milestones"]:
            self.plot_cum.add_milestone(m["date"], m["threshold"])

        self.plot_weekly.set_ylabel("Downloads")
        if s["weeks"]:
            self.plot_weekly.add_bars(*zip(*s["weeks"]), SUCCESS)

    # ---- export ---------------------------------------------------------
    def _export_charts(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, "Choose a folder for chart PNGs")
        if not dir_path:
            return
        try:
            written = []
            for slug, card in (("daily", self.plot_daily), ("cumulative", self.plot_cum), ("weekly", self.plot_weekly)):
                path = Path(dir_path) / f"analytics_{slug}.png"
                exporter = ImageExporter(card.plot.getPlotItem())
                exporter.parameters()["width"] = 1200
                exporter.export(str(path))
                written.append(path.name)
            QMessageBox.information(self, "Charts exported", "Saved:\n" + "\n".join(written))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Export failed", str(exc))

