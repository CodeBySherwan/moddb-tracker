"""ui/pages/dashboard.py"""

from typing import Any, Dict, List, Optional, Tuple
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QPushButton, QToolButton, QVBoxLayout, QWidget
import analytics
from tracker import CONFIG_FILE, save_config
from storage import Storage
from ui.theme import ACCENT, GRAY, SUCCESS
from ui.icons import INSIGHT_COLORS, INSIGHT_ICONS, _apply_shadow, _icon, _icon_label
from ui.widgets import ActivityFeed, StatCard

class DashboardPage(QWidget):
    view_insights = pyqtSignal()

    def __init__(self, config: Dict[str, Any], config_path: str = CONFIG_FILE, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config
        self._config_path = config_path
        self._storage: Optional[Storage] = None
        self._insights_available = False
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

        self.activity = ActivityFeed()
        layout.addWidget(self.activity, 1)

        self._apply_layout()

    # ---- rearrangement --------------------------------------------------
    def _build_customize_menu(self) -> QMenu:
        menu = QMenu(self)
        self._act_stats = QAction("Stat cards", self)
        self._act_insights = QAction("Insights", self)
        self._act_activity = QAction("Activity", self)
        for act, key in ((self._act_stats, "stats"), (self._act_insights, "insights"),
                         (self._act_activity, "activity")):
            act.setCheckable(True)
            act.toggled.connect(lambda on, k=key: self._set_pref(k, on))
            menu.addAction(act)
        return menu

    def _load_prefs(self) -> None:
        prefs = self._config.get("ui", {}).get("dashboard", {}) or {}
        self._prefs = {
            "stats": bool(prefs.get("stats", True)),
            "insights": bool(prefs.get("insights", True)),
            "activity": bool(prefs.get("activity", True)),
        }

    def _save_prefs(self) -> None:
        try:
            self._config.setdefault("ui", {}).setdefault("dashboard", {}).update(self._prefs)
            save_config(self._config, self._config_path)
        except Exception:  # noqa: BLE001
            pass

    def _sync_menu(self) -> None:
        for act, key in ((self._act_stats, "stats"), (self._act_insights, "insights"),
                         (self._act_activity, "activity")):
            act.setChecked(self._prefs[key])

    def _set_pref(self, key: str, value: bool) -> None:
        if self._prefs.get(key) == bool(value):
            return
        self._prefs[key] = bool(value)
        self._apply_layout()
        self._save_prefs()

    def _apply_layout(self) -> None:
        self.stats_host.setVisible(self._prefs["stats"])
        self.summary.setVisible(self._prefs["stats"])
        self.activity.setVisible(self._prefs["activity"])
        self.insights_panel.setVisible(self._prefs["insights"] and self._insights_available)
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
            lab.setStyleSheet(f"font-size: 12px; color: {GRAY}; background: transparent; border: none;")
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

    def refresh(self, storage: Optional[Storage] = None) -> None:
        if storage is not None:
            self._storage = storage
            self._update_stats(storage)
            self._update_insights(storage)
            self.activity.refresh(storage)

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
