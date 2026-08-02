"""ui/pages/charts.py"""

from typing import Any, Dict, List, Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget
import analytics
from tracker import CONFIG_FILE, save_config
from storage import Storage
from ui.theme import ACCENT, SUCCESS
from ui.theme import LINE_COLORS
from ui.widgets import PlotCard


class ChartsPage(QWidget):
    """Dashboard-style overview charts on their own tab, with a date-range selector."""

    regen_requested = pyqtSignal()
    MIN_COLUMN_WIDTH = 460
    DEFAULT_DAYS = 30
    RANGE_OPTIONS = (7, 14, 30, 60, 90)

    def __init__(self, config: Dict[str, Any], config_path: str = CONFIG_FILE, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config
        self._config_path = config_path
        self._storage: Optional[Storage] = None
        self._chart_cards: List["PlotCard"] = []
        self._current_cols = -1

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        title = QLabel("Charts")
        title.setObjectName("PageTitle")
        outer.addWidget(title)
        hint = QLabel("Overall download trends across all tracked items.")
        hint.setObjectName("Hint")
        outer.addWidget(hint)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        controls.addWidget(QLabel("Range:"))
        self.days_combo = QComboBox()
        for n in self.RANGE_OPTIONS:
            self.days_combo.addItem(f"Last {n} days", n)
        self.days_combo.setCurrentIndex(self._default_days_index())
        self.days_combo.currentIndexChanged.connect(self._days_changed)
        controls.addWidget(self.days_combo)
        controls.addStretch(1)
        self.regen_btn = QPushButton("Regenerate charts")
        self.regen_btn.clicked.connect(self._request_regen)
        controls.addWidget(self.regen_btn)
        outer.addLayout(controls)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.charts_host = QWidget()
        self.charts_grid = QGridLayout(self.charts_host)
        self.charts_grid.setSpacing(16)
        self.charts_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.charts_host)
        outer.addWidget(self.scroll, 1)

        self.placeholder = QLabel("No charts yet. Click \u201cPoll now\u201d to fetch data.")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setObjectName("Hint")
        self.placeholder.setMinimumHeight(220)

    # ---- data ------------------------------------------------------------
    def _default_days_index(self) -> int:
        days = int(self._config.get("ui", {}).get("charts_days", self.DEFAULT_DAYS))
        idx = self.days_combo.findData(days)
        return idx if idx >= 0 else self.days_combo.findData(self.DEFAULT_DAYS)

    def _days_changed(self) -> None:
        try:
            self._config.setdefault("ui", {})["charts_days"] = int(self.days_combo.currentData() or self.DEFAULT_DAYS)
            save_config(self._config, self._config_path)
        except Exception:  # noqa: BLE001
            pass
        self._reload_charts()

    def refresh(self, storage: Optional[Storage] = None) -> None:
        if storage is not None:
            self._storage = storage
        self._reload_charts()

    def reload(self) -> None:
        self._reload_charts()

    def _request_regen(self) -> None:
        self.regen_requested.emit()

    # ---- charts ----------------------------------------------------------
    def _reload_charts(self) -> None:
        while self.charts_grid.count():
            item = self.charts_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._chart_cards = []
        self._current_cols = -1

        storage = self._storage
        if storage is None:
            self.charts_grid.addWidget(self.placeholder, 0, 0)
            return

        days = int(self.days_combo.currentData() or self.DEFAULT_DAYS)
        per_day = analytics.dashboard_downloads_per_day(storage, days)
        totals = analytics.dashboard_total_downloads(storage, days)
        overview = analytics.dashboard_mod_overview(storage, days, top=5)
        comments = analytics.dashboard_comment_activity(storage, days)

        if not (per_day or overview or comments or any(v for _, v in totals)):
            self.charts_grid.addWidget(self.placeholder, 0, 0)
            return

        plot_daily = PlotCard("Downloads per day", "Bars: daily gain   \u00b7   line: 7-day average")
        plot_total = PlotCard("Total downloads", "Cumulative downloads across all tracked mods")
        plot_mods = PlotCard("Mod overview", "Latest tracked total per mod")
        plot_comments = PlotCard("Comment activity", "New comments per day")

        plot_daily.set_ylabel("Downloads")
        if per_day:
            plot_daily.add_bars(*zip(*per_day), ACCENT)
            ma = analytics.moving_average(per_day, 7)
            if ma:
                plot_daily.add_line(*zip(*ma), "#38BDF8", width=2)

        plot_total.set_ylabel("Total downloads")
        if totals:
            plot_total.add_line(*zip(*totals), ACCENT, width=2, fill=True)
            for milestone in analytics.milestones(totals):
                plot_total.add_milestone(milestone["date"], milestone["threshold"])

        plot_mods.set_ylabel("Downloads")
        for i, s in enumerate(overview):
            color = LINE_COLORS[i % len(LINE_COLORS)]
            plot_mods.add_line(*zip(*s["series"]), color, width=2, name=s["name"])

        plot_comments.set_ylabel("Comments")
        if comments:
            plot_comments.add_bars(*zip(*comments), SUCCESS)

        self._chart_cards = [plot_daily, plot_total, plot_mods, plot_comments]
        self._relayout()

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

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if not self._chart_cards:
            return
        if self._columns() != self._current_cols:
            self._relayout()
