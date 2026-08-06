"""ui/pages/comments.py"""

from typing import Any, Dict, List, Optional
from PyQt6.QtCore import QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QFontMetrics, QPainter, QPixmap
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget
from storage import Storage
from ui.theme import ACCENT, BORDER, CARD, FAINT, GRAY, LINE_COLORS, SURFACE, TEXT, WARNING
from ui.widgets import relative_time


def _avatar(author: str, size: int = 34) -> QLabel:
    """Circular avatar: author's first letter on a hash-picked background."""
    color = LINE_COLORS[abs(hash(author)) % len(LINE_COLORS)]
    letter = (author or "?")[0].upper()
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(0, 0, size, size)
    f = p.font()
    f.setPixelSize(int(size * 0.5))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#FFFFFF"))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, letter)
    p.end()
    lab = QLabel()
    lab.setPixmap(pm)
    lab.setFixedSize(size, size)
    return lab


def _chip(text: str, color: str) -> QLabel:
    lab = QLabel(text)
    lab.setStyleSheet(
        f"color: {color}; background-color: {color}22; font-size: 9px; font-weight: 800;"
        f" letter-spacing: 1px; border-radius: 4px; padding: 2px 7px; border: none;"
    )
    return lab


class CommentCard(QFrame):
    """One comment / reply as a card: avatar, author, mod chip, snippet, time."""

    clicked = pyqtSignal(object)
    open_requested = pyqtSignal(int)

    def __init__(self, comment: Dict[str, Any], mod_name: str, mod_url: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.mod_id = int(comment.get("mod_id") or 0)
        self.mod_url = mod_url
        self._selected = False
        self._reply = bool(comment.get("parent_id"))

        is_reply = self._reply
        color = WARNING if is_reply else ACCENT
        chip = "REPLY" if is_reply else "COMMENT"
        self.setStyleSheet(
            f"CommentCard {{ background-color: {CARD}; border: 1px solid {BORDER};"
            f" border-left: 4px solid {color}; border-radius: 10px; }}"
            f"CommentCard:hover {{ border-color: {ACCENT}; background-color: {SURFACE}; }}"
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        lay.addWidget(_avatar(comment.get("author") or "?", 34), 0, Qt.AlignmentFlag.AlignTop)

        body = QVBoxLayout()
        body.setSpacing(3)

        head = QHBoxLayout()
        head.setSpacing(8)
        author = QLabel(comment.get("author") or "unknown")
        author.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {TEXT}; background: transparent; border: none;")
        head.addWidget(author)
        head.addWidget(_chip(chip, color))
        head.addWidget(_chip(mod_name, GRAY))
        head.addStretch(1)
        stamp = QLabel(relative_time(comment.get("posted_at")))
        stamp.setStyleSheet(f"font-size: 11px; color: {FAINT}; background: transparent; border: none;")
        head.addWidget(stamp)
        body.addLayout(head)

        snippet = QLabel(" ".join((comment.get("content") or "").split())[:220])
        snippet.setWordWrap(True)
        snippet.setStyleSheet(f"font-size: 12px; color: {GRAY}; background: transparent; border: none;")
        metrics = QFontMetrics(snippet.font())
        snippet.setFixedHeight(metrics.lineSpacing() * 2)
        body.addWidget(snippet)

        lay.addLayout(body, 1)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.setStyleSheet(
            f"CommentCard {{ background-color: {SURFACE if selected else CARD};"
            f" border: 1px solid {ACCENT if selected else BORDER};"
            f" border-left: 4px solid {WARNING if self._reply else ACCENT};"
            f" border-radius: 10px; }}"
        )

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        super().mouseDoubleClickEvent(event)
        self.open_requested.emit(self.mod_id)


class CommentsPage(QWidget):
    PAGE_SIZE = 50
    MAX_ROWS = 150

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._filter = ""
        self._rows: List[Dict[str, Any]] = []
        self._filtered: List[Dict[str, Any]] = []
        self._shown = self.PAGE_SIZE
        self._mod_names: Dict[int, str] = {}
        self._mod_urls: Dict[int, str] = {}
        self._selected: Optional[CommentCard] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Comments & replies")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        hint = QLabel("All comments seen on your tracked items (newest first).")
        hint.setObjectName("Hint")
        layout.addWidget(hint)

        toolbar = QHBoxLayout()
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Filter: All", "Filter: Replies only", "Filter: New comments"])
        self.filter_combo.currentIndexChanged.connect(lambda _: self._apply_filter())
        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText("Search comments\u2026")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(240)
        self.search.textChanged.connect(lambda _: self._apply_filter())
        self.open_btn = QPushButton("Open selected on ModDB")
        self.open_btn.clicked.connect(self._open_selected)
        toolbar.addWidget(self.filter_combo)
        toolbar.addWidget(self.search)
        toolbar.addStretch(1)
        toolbar.addWidget(self.open_btn)
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

        self.placeholder = QLabel("No comments yet. Poll your tracked items to gather them.")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setObjectName("Hint")
        self.placeholder.setMinimumHeight(120)
        layout.addWidget(self.placeholder)
        self._storage = None

    def refresh(self, storage: Storage) -> None:
        self._storage = storage
        self._mod_names = {}
        self._mod_urls = {}
        for m in storage.get_mods(active_only=False):
            m = dict(m)
            self._mod_names[int(m["id"])] = str(m.get("name") or m["id"])
            self._mod_urls[int(m["id"])] = str(m.get("url") or "")
        self._rows = [dict(c) for c in storage.recent_comments(300)]
        self._shown = self.PAGE_SIZE
        self._selected = None
        self._apply_filter()

    def apply_filter(self, text: str) -> None:
        self.search.setText(text)
        self._apply_filter()

    def _apply_filter(self) -> None:
        needle = self.search.text().strip().lower()
        mode = self.filter_combo.currentIndex()
        out: List[Dict[str, Any]] = []
        for c in self._rows:
            is_reply = bool(c.get("parent_id"))
            if mode == 1 and not is_reply:
                continue
            if mode == 2 and is_reply:
                continue
            if needle:
                mod_name = self._mod_names.get(int(c.get("mod_id") or 0), str(c.get("mod_id")))
                hay = f"{mod_name} {c.get('author') or ''} {c.get('content') or ''}".lower()
                if needle not in hay:
                    continue
            out.append(c)
        self._filtered = out
        self._selected = None
        self._render()

    def _render(self) -> None:
        while self._cards.count() > 1:
            item = self._cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for c in self._filtered[: self._shown]:
            mod_id = int(c.get("mod_id") or 0)
            card = CommentCard(
                c,
                self._mod_names.get(mod_id, str(mod_id)),
                self._mod_urls.get(mod_id, ""),
            )
            card.clicked.connect(self._on_card_clicked)
            card.open_requested.connect(self._open_mod)
            self._cards.insertWidget(self._cards.count() - 1, card)
        remaining = len(self._filtered) - self._shown
        if remaining > 0:
            self.load_more.setText(f"Load more ({remaining} more)")
            self.load_more.setVisible(True)
        else:
            self.load_more.setVisible(False)
        has_rows = bool(self._rows)
        self.placeholder.setVisible(not has_rows)
        self.scroll.setVisible(has_rows)

    def _load_more(self) -> None:
        self._shown = min(self._shown + self.PAGE_SIZE, self.MAX_ROWS)
        self._render()

    def _on_card_clicked(self, card: CommentCard) -> None:
        if self._selected is not None and self._selected is not card:
            self._selected.set_selected(False)
        self._selected = card
        card.set_selected(True)

    def _open_selected(self) -> None:
        if self._selected is not None:
            self._open_mod(self._selected.mod_id)

    def _open_mod(self, mod_id: int) -> None:
        url = self._mod_urls.get(int(mod_id), "")
        if url:
            QDesktopServices.openUrl(QUrl(url))
