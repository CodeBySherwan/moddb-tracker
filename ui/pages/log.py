"""ui/pages/log.py"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
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
            "border-radius: 8px; font-family: Consolas, monospace; font-size: 12px; }}"
        )

