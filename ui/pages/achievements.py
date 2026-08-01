"""ui/pages/achievements.py"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
import datetime
from typing import Dict, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QProgressBar, QScrollArea, QVBoxLayout, QWidget
import analytics
from storage import Storage
from ui.theme import GRAY, SUCCESS, WARNING
from ui.widgets import BadgeCard, FlowLayout, section_label

class AchievementsPage(QWidget):
    """Milestone timeline and achievement badges for each tracked mod."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._storage: Optional[Storage] = None
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

        title = QLabel("Achievements")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        hint = QLabel("Milestone timeline and achievement badges for each tracked mod.")
        hint.setObjectName("Hint")
        layout.addWidget(hint)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel("Mod:"))
        self.mod_combo = QComboBox()
        self.mod_combo.setMinimumWidth(240)
        self.mod_combo.currentIndexChanged.connect(self._render)
        row.addWidget(self.mod_combo)
        row.addStretch(1)
        layout.addLayout(row)

        self.summary = QFrame()
        self.summary.setObjectName("Panel")
        sl = QHBoxLayout(self.summary)
        sl.setContentsMargins(14, 10, 14, 10)
        sl.setSpacing(24)
        self.sum_labels: Dict[str, QLabel] = {}
        for key, cap in (("total", "Total downloads"), ("first", "First seen"), ("span", "Days tracked"), ("avg", "Avg / day")):
            col = QVBoxLayout()
            col.setSpacing(2)
            c = QLabel(cap)
            c.setObjectName("Caption")
            v = QLabel("—")
            v.setStyleSheet("font-weight: 700; font-size: 16px; background: transparent; border: none;")
            self.sum_labels[key] = v
            col.addWidget(c)
            col.addWidget(v)
            sl.addLayout(col)
        sl.addStretch(1)
        layout.addWidget(self.summary)

        layout.addWidget(section_label("Milestones"))
        self.timeline = QFrame()
        self.timeline.setObjectName("Panel")
        self.tl_lay = QVBoxLayout(self.timeline)
        self.tl_lay.setContentsMargins(14, 12, 14, 12)
        self.tl_lay.setSpacing(8)
        layout.addWidget(self.timeline)

        layout.addWidget(section_label("Achievements"))
        self.badges_host = QWidget()
        self.badges_flow = FlowLayout(self.badges_host, spacing=10, min_width=220)
        layout.addWidget(self.badges_host)

        self.placeholder = QLabel("No tracked mods yet. Poll or add mods to see achievements.")
        self.placeholder.setObjectName("Hint")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setMinimumHeight(120)
        layout.addWidget(self.placeholder, 1)

        self.scroll.setWidget(content)
        outer.addWidget(self.scroll)

    def refresh(self, storage: Storage) -> None:
        self._storage = storage
        current = self.mod_combo.currentData()
        self.mod_combo.blockSignals(True)
        self.mod_combo.clear()
        for m in storage.get_mods(active_only=True):
            self.mod_combo.addItem(m["name"], int(m["id"]))
        if current is not None:
            idx = self.mod_combo.findData(current)
            if idx >= 0:
                self.mod_combo.setCurrentIndex(idx)
        self.mod_combo.blockSignals(False)
        self._render()

    def _render(self) -> None:
        storage = self._storage
        has = storage is not None and self.mod_combo.count() > 0
        self.summary.setVisible(has)
        self.timeline.setVisible(has)
        self.badges_host.setVisible(has)
        self.placeholder.setVisible(not has)
        if not has:
            return
        data = analytics.achievements(storage, int(self.mod_combo.currentData()))
        tl = data["milestones"]
        self.sum_labels["total"].setText(f"{tl['total']:,}")
        self.sum_labels["first"].setText(str(tl["first_seen"] or "—"))
        span = (datetime.date.today() - tl["first_seen"]).days + 1 if tl["first_seen"] else 0
        self.sum_labels["span"].setText(f"{span:,}" if span else "—")
        self.sum_labels["avg"].setText(f"{tl['avg_per_day']:,}")

        while self.tl_lay.count():
            item = self.tl_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for m in tl["reached"]:
            self.tl_lay.addWidget(self._tl_row(
                f"◆ {m['threshold']:,} downloads",
                f"Reached {m['date']} — {m['days']} days after the previous one ({m['per_day']} per day).",
                SUCCESS))
        if tl["next"]:
            n = tl["next"]
            eta = f"~{n['eta_days']} days at {n['avg_per_day']}/day" if n["eta_days"] else "pace too slow to estimate"
            self.tl_lay.addWidget(self._tl_row(
                f"◇ {n['threshold']:,} downloads",
                f"{n['total']:,} so far — {n['remaining']:,} to go ({eta}).",
                WARNING, progress=n["total"] / n["threshold"]))
        if not tl["reached"] and not tl["next"]:
            self.tl_lay.addWidget(self._tl_row("No milestones yet", "Keep polling — milestones appear as downloads grow.", GRAY))
        self.tl_lay.addStretch(1)

        self.badges_flow.clear()
        for b in data["achievements"]:
            self.badges_flow.add_card(BadgeCard(b))

    @staticmethod
    def _tl_row(title: str, detail: str, color: str, progress: Optional[float] = None) -> QFrame:
        row = QFrame()
        row.setObjectName("EventRow")
        h = QHBoxLayout(row)
        h.setContentsMargins(4, 4, 4, 4)
        h.setSpacing(12)
        dot = QLabel()
        dot.setFixedSize(12, 12)
        dot.setStyleSheet(f"background: {color}; border-radius: 6px; border: none;")
        h.addWidget(dot)
        col = QVBoxLayout()
        col.setSpacing(1)
        t = QLabel(title)
        t.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {color}; background: transparent; border: none;")
        col.addWidget(t)
        d = QLabel(detail)
        d.setWordWrap(True)
        d.setStyleSheet(f"color: {GRAY}; font-size: 11px; background: transparent; border: none;")
        col.addWidget(d)
        if progress is not None:
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(int(min(1.0, progress) * 1000))
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            col.addWidget(bar)
        h.addLayout(col, 1)
        return row

