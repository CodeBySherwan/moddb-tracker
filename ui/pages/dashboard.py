"""ui/pages/dashboard.py"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from typing import Any, Dict, List, Optional, Tuple
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget
import analytics
from tracker import CONFIG_FILE, save_config
from storage import Storage
from ui.theme import ACCENT, GRAY, SUCCESS
from ui.icons import INSIGHT_COLORS, INSIGHT_ICONS, _apply_shadow, _icon, _icon_label
from ui.widgets import ActivityFeed, PlotCard, StatCard, section_label

# cross-page chart palette lives in ui.theme
from ui.theme import LINE_COLORS  # noqa: E402

class DashboardPage(QWidget):
    regen_requested = pyqtSignal()
    view_insights = pyqtSignal()
    DASH_DAYS = 30
    MIN_COLUMN_WIDTH = 460

    def __init__(self, config: Dict[str, Any], config_path: str = CONFIG_FILE, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config
        self._config_path = config_path
        self._storage: Optional[Storage] = None
        self._insights_available = False
        self._chart_cards: List["PlotCard"] = []
        self._current_cols = -1
        self._load_prefs()

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
        self.customize_btn = QToolButton()
        self.customize_btn.setText("Customize \u25be")
        self.customize_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.customize_btn.setToolTip("Rearrange dashboard widgets")
        self.customize_btn.setMenu(self._build_customize_menu())
        header.addWidget(self.customize_btn)
        layout.addLayout(header)

        self.stats_host = QWidget()
        self.stat_grid = QGridLayout(self.stats_host)
        self.stat_grid.setSpacing(12)
        self.stat_cards: Dict[str, StatCard] = {}
        for key, caption in [
            ("total", "Total downloads"),
            ("today", "Downloads today"),
            ("week", "This week"),
            ("month", "This month"),
        ]:
            card = StatCard(caption)
            self.stat_cards[key] = card
        for i, key in enumerate(["total", "today", "week", "month"]):
            self.stat_grid.addWidget(self.stat_cards[key], 0, i)
        layout.addWidget(self.stats_host)

        self.summary = QFrame()
        self.summary.setObjectName("Panel")
        sm = QHBoxLayout(self.summary)
        sm.setContentsMargins(16, 10, 16, 10)
        sm.setSpacing(24)
        self._sum: Dict[str, Tuple[QLabel, QLabel]] = {}
        for key, caption in [("avg", "AVG / DAY"), ("comments", "COMMENTS"),
                             ("replies", "REPLIES"), ("fastest", "FASTEST GROWING")]:
            col = QVBoxLayout()
            col.setSpacing(2)
            val = QLabel("—")
            val.setStyleSheet("font-size: 16px; font-weight: 700; border: none; background: transparent;")
            cap = QLabel(caption)
            cap.setObjectName("StatCaption")
            col.addWidget(val)
            col.addWidget(cap)
            self._sum[key] = (val, cap)
            sm.addLayout(col, 1)
        _apply_shadow(self.summary, 16, 2, alpha=50)
        layout.addWidget(self.summary)

        self._build_insights_strip()
        layout.addWidget(self.insights_panel)

        self.charts_section = self._build_charts_section()
        self.body = QHBoxLayout()
        self.body.setSpacing(12)
        self.body.addWidget(self.charts_section, 1)
        self.activity = ActivityFeed()
        self.activity.setFixedWidth(320)
        self.body.addWidget(self.activity)
        layout.addLayout(self.body, 1)

        self.below_row = QHBoxLayout()
        self.below_row.setSpacing(12)
        layout.addLayout(self.below_row)

        self._apply_layout()

    # ---- rearrangement --------------------------------------------------
    def _build_customize_menu(self) -> QMenu:
        menu = QMenu(self)
        self._act_stats = QAction("Stat cards", self)
        self._act_insights = QAction("Insights", self)
        self._act_charts = QAction("Charts", self)
        self._act_activity = QAction("Activity", self)
        for act, key in ((self._act_stats, "stats"), (self._act_insights, "insights"),
                         (self._act_charts, "charts"), (self._act_activity, "activity")):
            act.setCheckable(True)
            act.toggled.connect(lambda on, k=key: self._set_pref(k, on))
            menu.addAction(act)
        menu.addSeparator()
        sub = menu.addMenu("Activity position")
        self._act_pos_right = QAction("Right side", self)
        self._act_pos_below = QAction("Below charts", self)
        for act, pos in ((self._act_pos_right, "right"), (self._act_pos_below, "below")):
            act.setCheckable(True)
            act.triggered.connect(lambda _, p=pos: self._set_activity_position(p))
            sub.addAction(act)
        return menu

    def _load_prefs(self) -> None:
        prefs = self._config.get("ui", {}).get("dashboard", {}) or {}
        self._prefs = {
            "stats": bool(prefs.get("stats", True)),
            "insights": bool(prefs.get("insights", True)),
            "charts": bool(prefs.get("charts", True)),
            "activity": bool(prefs.get("activity", True)),
            "activity_position": "below" if prefs.get("activity_position") == "below" else "right",
        }

    def _save_prefs(self) -> None:
        try:
            self._config.setdefault("ui", {}).setdefault("dashboard", {}).update(self._prefs)
            save_config(self._config, self._config_path)
        except Exception:  # noqa: BLE001
            pass

    def _sync_menu(self) -> None:
        for act, key in ((self._act_stats, "stats"), (self._act_insights, "insights"),
                         (self._act_charts, "charts"), (self._act_activity, "activity")):
            act.setChecked(self._prefs[key])
        self._act_pos_right.setChecked(self._prefs["activity_position"] == "right")
        self._act_pos_below.setChecked(self._prefs["activity_position"] == "below")

    def _set_pref(self, key: str, value: bool) -> None:
        if self._prefs.get(key) == bool(value):
            return
        self._prefs[key] = bool(value)
        self._apply_layout()
        self._save_prefs()

    def _set_activity_position(self, pos: str) -> None:
        if self._prefs["activity_position"] == pos:
            return
        self._prefs["activity_position"] = pos
        self._move_activity()
        self._sync_menu()
        self._save_prefs()

    def _move_activity(self) -> None:
        pos = self._prefs["activity_position"]
        is_below = self.below_row.indexOf(self.activity) >= 0
        if pos == "below":
            if not is_below:
                self.body.removeWidget(self.activity)
                self.below_row.addWidget(self.activity, 1)
            self.activity.setFixedWidth(0)
            self.activity.setMaximumHeight(230)
        else:
            if is_below:
                self.below_row.removeWidget(self.activity)
                self.body.addWidget(self.activity)
            self.activity.setFixedWidth(320)
            self.activity.setMaximumHeight(16777215)

    def _apply_layout(self) -> None:
        self.stats_host.setVisible(self._prefs["stats"])
        self.summary.setVisible(self._prefs["stats"])
        self.charts_section.setVisible(self._prefs["charts"])
        self.activity.setVisible(self._prefs["activity"])
        self.insights_panel.setVisible(self._prefs["insights"] and self._insights_available)
        self._move_activity()
        self._sync_menu()

    def _build_insights_strip(self) -> None:
        self.insights_panel = QFrame()
        self.insights_panel.setObjectName("Panel")
        ins = QHBoxLayout(self.insights_panel)
        ins.setContentsMargins(14, 10, 14, 10)
        ins.setSpacing(16)
        label = QLabel("INSIGHTS")
        label.setObjectName("SectionTitle")
        ins.addWidget(label)
        self.insight_items: List[QLabel] = []
        self.insight_icons: List[QLabel] = []
        for _ in range(3):
            wrap2 = QWidget()
            wrap2.setStyleSheet("background: transparent; border: none;")
            h2 = QHBoxLayout(wrap2)
            h2.setContentsMargins(0, 0, 0, 0)
            h2.setSpacing(8)
            icon_lab = _icon_label("info", ACCENT, 16)
            lab = QLabel("—")
            lab.setWordWrap(True)
            lab.setStyleSheet("font-size: 12px; color: #334155; background: transparent; border: none;")
            h2.addWidget(icon_lab, 0, Qt.AlignmentFlag.AlignTop)
            h2.addWidget(lab, 1)
            self.insight_icons.append(icon_lab)
            self.insight_items.append(lab)
            ins.addWidget(wrap2, 1)
        view_all = QPushButton("View all")
        view_all.setCursor(Qt.CursorShape.PointingHandCursor)
        view_all.clicked.connect(self._request_insights)
        ins.addWidget(view_all)
        self.insights_panel.setVisible(False)
        _apply_shadow(self.insights_panel, 16, 2, alpha=50)

    def _build_charts_section(self) -> QWidget:
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(8)
        chart_header = QHBoxLayout()
        chart_header.addWidget(section_label("Charts"))
        chart_header.addStretch(1)
        self.regen_btn = QPushButton("Regenerate charts")
        self.regen_btn.clicked.connect(self._request_regen)
        chart_header.addWidget(self.regen_btn)
        wl.addLayout(chart_header)
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
            self._storage = storage
            self._update_stats(storage)
            self._update_insights(storage)
            self.activity.refresh(storage)
        self._reload_charts()

    def _request_regen(self) -> None:
        self.regen_requested.emit()

    def _request_insights(self) -> None:
        self.view_insights.emit()

    def _update_insights(self, storage: Storage) -> None:
        insights = analytics.generate_insights(storage, 30, limit=3)
        self._insights_available = bool(insights)
        self.insights_panel.setVisible(self._prefs["insights"] and self._insights_available)
        for i, lab in enumerate(self.insight_items):
            if i < len(insights):
                kind = insights[i].get("kind", "info")
                self.insight_icons[i].setPixmap(
                    _icon(INSIGHT_ICONS.get(kind, "info"), INSIGHT_COLORS.get(kind, ACCENT), 16)
                )
                lab.setText(f"{insights[i]['title']} — {insights[i]['detail']}")
            else:
                lab.setText("")

    def reload(self) -> None:
        self._reload_charts()

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

        days = self.DASH_DAYS
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

        plot_mods.set_ylabel("Downloads")
        for i, s in enumerate(overview):
            color = LINE_COLORS[i % len(LINE_COLORS)]
            plot_mods.add_line(*zip(*s["series"]), color, width=2, name=s["name"])

        plot_comments.set_ylabel("Comments")
        if comments:
            plot_comments.add_bars(*zip(*comments), SUCCESS)

        self._chart_cards = [plot_daily, plot_total, plot_mods, plot_comments]
        self._relayout()

    def _update_stats(self, storage: Storage) -> None:
        s = storage.dashboard_stats()
        today = int(s["today_downloads"] or 0)
        self.stat_cards["total"].set_value(s["total_downloads"], f"▲ +{today:,} today", SUCCESS)
        self.stat_cards["today"].set_value(today, "across all tracked items", GRAY)
        self.stat_cards["week"].set_value(s["week_downloads"], "last 7 days", GRAY)
        self.stat_cards["month"].set_value(s["month_downloads"], f"{int(s['avg_per_day'] or 0)} per day", GRAY)
        avg = int(s["avg_per_day"] or 0)
        self._sum["avg"][0].setText(f"{avg:,}")
        self._sum["comments"][0].setText(f"{int(s['comments'] or 0):,}")
        self._sum["replies"][0].setText(f"{int(s['replies'] or 0):,}")
        fastest_note = f"+{int(s['fastest_delta'] or 0):,} this week" if s["fastest_mod"] else "no growth yet"
        self._sum["fastest"][0].setText(s["fastest_mod"] or "—")
        self._sum["fastest"][0].setStyleSheet(
            f"font-size: 16px; font-weight: 700; border: none; background: transparent;"
            f" color: {SUCCESS if s['fastest_mod'] else GRAY};"
        )

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

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if not self._chart_cards:
            return
        if self._columns() != self._current_cols:
            self._relayout()

