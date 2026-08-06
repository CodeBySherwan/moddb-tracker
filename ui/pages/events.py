"""ui/pages/events.py"""

from typing import Any, Dict, List, Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget
from storage import Storage
from ui.theme import ACCENT, BORDER, CARD, FAINT, GRAY, SUCCESS, SURFACE, TEXT, WARNING
from ui.icons import _icon_label
from ui.widgets import relative_time

def _kind_style(kind: str) -> tuple:
    if kind == "download":
        return "download", SUCCESS
    if kind == "comment":
        return "chat", ACCENT
    if kind == "reply":
        return "reply", WARNING
    return "dot", GRAY


def _chip(text: str, color: str) -> QLabel:
    lab = QLabel(text)
    lab.setStyleSheet(
        f"color: {color}; background-color: {color}22; font-size: 9px; font-weight: 800;"
        f" letter-spacing: 1px; border-radius: 4px; padding: 2px 7px; border: none;"
    )
    return lab


class EventCard(QFrame):
    """One notification as a card: kind icon, mod name, message, time."""

    clicked = pyqtSignal(object)
    open_requested = pyqtSignal(str)

    def __init__(self, event: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.url = str(event.get("url") or "")
        self._selected = False
        self._unseen = bool(event.get("seen") is False)

        kind = str(event.get("kind") or "download")
        icon_name, color = _kind_style(kind)
        self._color = color
        kind_label = {"download": "DOWNLOADS", "comment": "COMMENT", "reply": "REPLY"}.get(kind, kind.upper())

        border_color = ACCENT if self._unseen else BORDER
        self.setStyleSheet(
            f"EventCard {{ background-color: {CARD}; border: 1px solid {border_color};"
            f" border-left: 4px solid {color}; border-radius: 10px; }}"
            f"EventCard:hover {{ border-color: {ACCENT}; background-color: {SURFACE}; }}"
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        icon = _icon_label(icon_name, color, 22)
        lay.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

        body = QVBoxLayout()
        body.setSpacing(3)

        head = QHBoxLayout()
        head.setSpacing(8)
        mod = QLabel(str(event.get("mod_name") or "ModDB"))
        weight = 700 if self._unseen else 600
        mod.setStyleSheet(f"font-size: 13px; font-weight: {weight}; color: {TEXT}; background: transparent; border: none;")
        head.addWidget(mod)
        head.addWidget(_chip(kind_label, color))
        head.addStretch(1)
        stamp = QLabel(relative_time(event.get("created_at")))
        stamp.setStyleSheet(f"font-size: 11px; color: {FAINT}; background: transparent; border: none;")
        head.addWidget(stamp)
        body.addLayout(head)

        message = QLabel(" ".join((str(event.get("message") or "")).split()))
        message.setWordWrap(True)
        message.setStyleSheet(f"font-size: 12px; color: {GRAY}; background: transparent; border: none;")
        body.addWidget(message)

        lay.addLayout(body, 1)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.setStyleSheet(
            f"EventCard {{ background-color: {SURFACE if selected else CARD};"
            f" border: 1px solid {ACCENT if selected else BORDER};"
            f" border-left: 4px solid {self._color};"
            f" border-radius: 10px; }}"
        )

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        super().mouseDoubleClickEvent(event)
        if self.url:
            self.open_requested.emit(self.url)


class EventsPage(QWidget):
    """Notification center: unseen highlighting, kind filter, mark-as-read, open on ModDB."""

    open_url = pyqtSignal(str)
    events_read = pyqtSignal()

    PAGE_SIZE = 50
    MAX_ROWS = 200

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._filter = ""
        self._kind = ""
        self._rows: List[Dict[str, Any]] = []
        self._displayed: List[Dict[str, Any]] = []
        self._shown = self.PAGE_SIZE
        self._selected: Optional[EventCard] = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        title = QLabel("Notifications")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        hint = QLabel("Download and comment events detected by polls. Double-click a card to open it on ModDB.")
        hint.setObjectName("Hint")
        layout.addWidget(hint)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText("Search events\u2026")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(240)
        self.search.textChanged.connect(lambda _: self._apply_filter())
        toolbar.addWidget(self.search)
        self.kind_combo = QComboBox()
        self.kind_combo.addItem("All kinds", "")
        self.kind_combo.addItem("Downloads", "download")
        self.kind_combo.addItem("Comments", "comment")
        self.kind_combo.addItem("Replies", "reply")
        self.kind_combo.currentIndexChanged.connect(lambda _: self._apply_filter())
        toolbar.addWidget(self.kind_combo)
        toolbar.addStretch(1)
        self.mark_read_btn = QPushButton("Mark all read")
        self.mark_read_btn.clicked.connect(self.mark_all_seen)
        toolbar.addWidget(self.mark_read_btn)
        layout.addLayout(toolbar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self._cards = QVBoxLayout(container)
        self._cards.setContentsMargins(2, 2, 2, 2)
        self._cards.setSpacing(8)
        self.load_more = QPushButton("Load more")
        self.load_more.setCursor(Qt.CursorShape.PointingHandCursor)
        self.load_more.clicked.connect(self._load_more)
        self._cards.addWidget(self.load_more)
        self.scroll.setWidget(container)
        layout.addWidget(self.scroll, 1)

        self.placeholder = QLabel("No events yet. Run a poll to start recording activity.")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setObjectName("Hint")
        self.placeholder.setMinimumHeight(120)
        layout.addWidget(self.placeholder)
        self._storage: Optional[Storage] = None

    def refresh(self, storage: Storage) -> None:
        self._storage = storage
        rows: List[Dict[str, Any]] = []
        for e in storage.recent_events(self.MAX_ROWS):
            rows.append({
                "id": e["id"],
                "created_at": e["created_at"],
                "kind": e["kind"],
                "mod_name": e["mod_name"] or "-",
                "message": e["message"],
                "url": e["url"] or "",
                "seen": bool(e["seen"]),
            })
        self._rows = rows
        self._shown = self.PAGE_SIZE
        self._selected = None
        self._apply_filter()

    def mark_all_seen(self) -> None:
        storage = getattr(self, "_storage", None)
        if storage is not None:
            storage.mark_events_seen()
        for r in self._rows:
            r["seen"] = True
        self._apply_filter()
        self.events_read.emit()

    def apply_filter(self, text: str) -> None:
        self.search.setText(text)
        self._apply_filter()

    def _mark_all_read(self) -> None:
        self.mark_all_seen()

    def _load_more(self) -> None:
        self._shown = min(self._shown + self.PAGE_SIZE, self.MAX_ROWS)
        self._render()

    def _apply_filter(self) -> None:
        needle = self.search.text().strip().lower()
        self._kind = self.kind_combo.currentData() or ""
        out = []
        for r in self._rows:
            if self._kind and r["kind"] != self._kind:
                continue
            if needle and needle not in f"{r['kind']} {r['mod_name']} {r['message']}".lower():
                continue
            out.append(r)
        self._displayed = out
        self._selected = None
        self._render()

    def _render(self) -> None:
        while self._cards.count() > 1:
            item = self._cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for r in self._displayed[: self._shown]:
            card = EventCard(r)
            card.clicked.connect(self._on_card_clicked)
            card.open_requested.connect(self.open_url)
            self._cards.insertWidget(self._cards.count() - 1, card)
        remaining = len(self._displayed) - self._shown
        self.load_more.setVisible(remaining > 0)
        if remaining > 0:
            self.load_more.setText(f"Load more ({remaining} more)")

        has_rows = bool(self._rows)
        self.placeholder.setVisible(not has_rows)
        self.scroll.setVisible(has_rows)

    def _on_card_clicked(self, card: EventCard) -> None:
        if self._selected is not None and self._selected is not card:
            self._selected.set_selected(False)
        self._selected = card
        card.set_selected(True)
