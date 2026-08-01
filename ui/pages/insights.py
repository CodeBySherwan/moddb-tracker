"""ui/pages/insights.py"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget
import analytics
from storage import Storage
from ui.widgets import InsightCard

class InsightsPage(QWidget):
    """Feed of rule-based insight cards generated from recent history."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Insights")
        title.setObjectName("PageTitle")
        hint = QLabel("Automated takeaways from your recent history (plain math, no AI).")
        hint.setObjectName("Hint")
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(title)
        col.addWidget(hint)
        header.addLayout(col)
        header.addStretch(1)
        layout.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        host = QWidget()
        self.feed = QVBoxLayout(host)
        self.feed.setContentsMargins(0, 0, 8, 0)
        self.feed.setSpacing(10)
        self.feed.addStretch(1)
        self.scroll.setWidget(host)
        layout.addWidget(self.scroll, 1)

        self.placeholder = QLabel("No insights yet. Poll a few days of data first.")
        self.placeholder.setObjectName("Hint")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def refresh(self, storage: Storage) -> None:
        while self.feed.count():
            item = self.feed.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        insights = analytics.generate_insights(storage, 30)
        if not insights:
            self.feed.addWidget(self.placeholder)
        else:
            for ins in insights:
                self.feed.addWidget(InsightCard(ins))
        self.feed.addStretch(1)

