"""ui/pages/log.py"""

from typing import Optional
from PyQt6.QtWidgets import QPlainTextEdit, QWidget
from ui.theme import BORDER, GRAY, PANEL

class LogPage(QPlainTextEdit):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(3000)
        self.setStyleSheet(
            f"QPlainTextEdit {{ background: {PANEL}; color: {GRAY}; border: 1px solid {BORDER};"
            "border-radius: 8px; font-family: Consolas, monospace; font-size: 12px; }"
        )

