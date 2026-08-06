"""Theme: palette dicts, dynamic accessors, and the global stylesheet builder.

Colors are looked up through the module-level ``__getattr__`` (PEP 562) so that
``from ui.theme import ACCENT`` resolves to the *active* theme's value at import
time. The theme is chosen once at startup (see ``ui.main_window``) and only
applies after a restart, so every import in the process binds one coherent
palette.
"""

from typing import Any, Dict


# --------------------------------------------------------------------------
# palettes
# --------------------------------------------------------------------------
DARK: Dict[str, str] = {
    "BG": "#0F172A",
    "CARD": "#1E293B",
    "PANEL": "#1E293B",
    "PANEL2": "#243247",
    "SURFACE": "#273449",
    "BORDER": "#334155",
    "TEXT": "#E2E8F0",
    "GRAY": "#94A3B8",
    "FAINT": "#64748B",
    "ACCENT": "#3B82F6",
    "ACCENT_DARK": "#2563EB",
    "SUCCESS": "#22C55E",
    "WARNING": "#F59E0B",
    "ERROR": "#EF4444",
    "line_colors": ["#3B82F6", "#22C55E", "#F59E0B", "#A78BFA", "#38BDF8", "#F472B6", "#FB923C", "#34D399"],
}

LIGHT: Dict[str, str] = {
    "BG": "#F1F5F9",
    "CARD": "#FFFFFF",
    "PANEL": "#FFFFFF",
    "PANEL2": "#E2E8F0",
    "SURFACE": "#F8FAFC",
    "BORDER": "#CBD5E1",
    "TEXT": "#0F172A",
    "GRAY": "#64748B",
    "FAINT": "#94A3B8",
    "ACCENT": "#2563EB",
    "ACCENT_DARK": "#1D4ED8",
    "SUCCESS": "#16A34A",
    "WARNING": "#D97706",
    "ERROR": "#DC2626",
    "line_colors": ["#2563EB", "#16A34A", "#D97706", "#7C3AED", "#0284C7", "#DB2777", "#EA580C", "#0D9488"],
}

NORD: Dict[str, str] = {
    "BG": "#2E3440",
    "CARD": "#3B4252",
    "PANEL": "#3B4252",
    "PANEL2": "#434C5E",
    "SURFACE": "#4C566A",
    "BORDER": "#434C5E",
    "TEXT": "#ECEFF4",
    "GRAY": "#D8DEE9",
    "FAINT": "#7B88A1",
    "ACCENT": "#5E81AC",
    "ACCENT_DARK": "#4C6A94",
    "SUCCESS": "#A3BE8C",
    "WARNING": "#EBCB8B",
    "ERROR": "#BF616A",
    "line_colors": ["#8FBCBB", "#81A1C1", "#A3BE8C", "#D08770", "#B48EAD", "#88C0D0", "#EBCB8B", "#BF616A"],
}

NORD_LIGHT: Dict[str, str] = {
    "BG": "#ECEFF4",
    "CARD": "#FFFFFF",
    "PANEL": "#FFFFFF",
    "PANEL2": "#E5E9F0",
    "SURFACE": "#E5E9F0",
    "BORDER": "#D8DEE9",
    "TEXT": "#2E3440",
    "GRAY": "#4C566A",
    "FAINT": "#7B88A1",
    "ACCENT": "#5E81AC",
    "ACCENT_DARK": "#4C6A94",
    "SUCCESS": "#4F7A45",
    "WARNING": "#A2760E",
    "ERROR": "#BF616A",
    "line_colors": ["#3B6EA5", "#2F7A4D", "#9A6B00", "#B44E8C", "#6C56C8", "#0E7E93", "#B0560E", "#BF3A42"],
}

DRACULA: Dict[str, str] = {
    "BG": "#282A36",
    "CARD": "#21222C",
    "PANEL": "#21222C",
    "PANEL2": "#343746",
    "SURFACE": "#44475A",
    "BORDER": "#44475A",
    "TEXT": "#F8F8F2",
    "GRAY": "#6272A4",
    "FAINT": "#53566F",
    "ACCENT": "#6272A4",
    "ACCENT_DARK": "#4B5A8A",
    "SUCCESS": "#50FA7B",
    "WARNING": "#F1FA8C",
    "ERROR": "#FF5555",
    "line_colors": ["#BD93F9", "#50FA7B", "#FFB86C", "#FF79C6", "#8BE9FD", "#F1FA8C", "#FF5555", "#6272A4"],
}

SOLARIZED_DARK: Dict[str, str] = {
    "BG": "#002B36",
    "CARD": "#073642",
    "PANEL": "#073642",
    "PANEL2": "#0A3A46",
    "SURFACE": "#0E4654",
    "BORDER": "#586E75",
    "TEXT": "#EEE8D5",
    "GRAY": "#93A1A1",
    "FAINT": "#657B83",
    "ACCENT": "#268BD2",
    "ACCENT_DARK": "#1D6FA8",
    "SUCCESS": "#859900",
    "WARNING": "#B58900",
    "ERROR": "#DC322F",
    "line_colors": ["#268BD2", "#859900", "#B58900", "#D33682", "#6C71C4", "#2AA198", "#CB4B16", "#DC322F"],
}

SOLARIZED_LIGHT: Dict[str, str] = {
    "BG": "#FDF6E3",
    "CARD": "#FFFFFF",
    "PANEL": "#FFFFFF",
    "PANEL2": "#E7E0CB",
    "SURFACE": "#F0EAD7",
    "BORDER": "#93A1A1",
    "TEXT": "#002B36",
    "GRAY": "#586E75",
    "FAINT": "#93A1A1",
    "ACCENT": "#268BD2",
    "ACCENT_DARK": "#1D6FA8",
    "SUCCESS": "#5A7D00",
    "WARNING": "#A06E00",
    "ERROR": "#DC322F",
    "line_colors": ["#1D6FA8", "#5A7D00", "#A06E00", "#C1285F", "#5C64C0", "#177D92", "#A8420F", "#C0262E"],
}

THEMES: Dict[str, Dict[str, str]] = {
    "dark": DARK,
    "light": LIGHT,
    "nord": NORD,
    "nord-light": NORD_LIGHT,
    "dracula": DRACULA,
    "solarized-dark": SOLARIZED_DARK,
    "solarized-light": SOLARIZED_LIGHT,
}

DISPLAY_NAMES: Dict[str, str] = {
    "dark": "Dark",
    "light": "Light",
    "nord": "Nord",
    "nord-light": "Nord Light",
    "dracula": "Dracula",
    "solarized-dark": "Solarized Dark",
    "solarized-light": "Solarized Light",
}

_ACTIVE_NAME = "dark"

# Names captured with ``from ui.theme import X`` that refresh_bindings() keeps
# in sync across already-imported modules after a live theme switch.
_REBIND_KEYS: tuple = tuple(DARK.keys()) + ("LINE_COLORS", "QSS")

# Modules that define their own constants with the same names (e.g. the
# matplotlib export charts stay dark) and must not be touched.
_SKIP_MODULES = {"charts"}


# --------------------------------------------------------------------------
# theme selection
# --------------------------------------------------------------------------
def set_theme(name: str) -> None:
    """Select the active palette by name (applies live, no restart needed)."""
    global _ACTIVE_NAME
    if name not in THEMES:
        name = "dark"
    _ACTIVE_NAME = name


def current_theme_name() -> str:
    return _ACTIVE_NAME


def current_theme() -> Dict[str, str]:
    return THEMES[_ACTIVE_NAME]


# --------------------------------------------------------------------------
# stylesheet
# --------------------------------------------------------------------------
def build_qss(palette: Dict[str, str]) -> str:
    BG = palette["BG"]
    CARD = palette["CARD"]
    PANEL = palette["PANEL"]
    PANEL2 = palette["PANEL2"]
    SURFACE = palette["SURFACE"]
    BORDER = palette["BORDER"]
    TEXT = palette["TEXT"]
    GRAY = palette["GRAY"]
    FAINT = palette["FAINT"]
    ACCENT = palette["ACCENT"]
    ACCENT_DARK = palette["ACCENT_DARK"]
    SUCCESS = palette["SUCCESS"]
    WARNING = palette["WARNING"]
    ERROR = palette["ERROR"]

    return f"""
* {{
    outline: none;
}}
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "Segoe UI";
    font-size: 13px;
}}
QLabel {{ background: transparent; }}

QFrame#Panel, QFrame#PanelSecondary {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QFrame#TopBar {{
    background-color: {BG};
    border-bottom: 1px solid {BORDER};
    border-radius: 0px;
}}
QFrame#StatCard, QFrame#ModCard {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#StatCard:hover {{
    border: 1px solid {ACCENT};
    background-color: {SURFACE};
}}
QFrame#ModCard:hover {{
    border: 1px solid {ACCENT};
    background-color: {SURFACE};
}}
QFrame#BadgeCard {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QFrame#BadgeCard:hover {{ border-color: {ACCENT}; }}
QFrame#EventRow {{
    background-color: transparent;
    border: none;
}}
QFrame#EventRow:hover {{ background-color: {PANEL2}; border-radius: 6px; }}

QPushButton {{
    background-color: {PANEL2};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 7px 14px;
    font-weight: 600;
}}
QPushButton:hover {{ border-color: {ACCENT}; background-color: {SURFACE}; }}
QPushButton:pressed {{ background-color: {BORDER}; }}
QPushButton:disabled {{ color: {FAINT}; border-color: {BORDER}; background-color: {PANEL2}; }}
QPushButton#Primary {{
    background-color: {ACCENT};
    border: none;
    color: #FFFFFF;
}}
QPushButton#Primary:hover {{ background-color: {ACCENT_DARK}; }}
QPushButton#Primary:disabled {{ background-color: {PANEL2}; color: {FAINT}; }}
QPushButton#Danger:hover {{ border-color: {ERROR}; color: {ERROR}; }}

QPushButton#CardAction {{
    padding: 3px 9px;
    font-size: 12px;
    border-radius: 6px;
}}
QPushButton#CardAction:hover {{ border-color: {ACCENT}; background-color: {SURFACE}; }}

QToolButton {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 4px 8px;
    font-weight: 600;
}}
QToolButton:hover {{ background-color: {PANEL2}; color: {ACCENT}; }}

QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background-color: {PANEL2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit#Search {{
    border-radius: 18px;
    padding: 7px 16px;
    background-color: {PANEL2};
    border: 1px solid {BORDER};
}}
QLineEdit#Search:focus {{ border: 1px solid {ACCENT}; }}

QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {GRAY};
    margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background-color: {PANEL2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    selection-background-color: {ACCENT};
    selection-color: #FFFFFF;
}}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 17px;
    height: 17px;
    border: 2px solid {BORDER};
    border-radius: 4px;
    background-color: {PANEL2};
}}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    image: none;
}}

QTableWidget {{
    background-color: {CARD};
    alternate-background-color: {PANEL2};
    border: 1px solid {BORDER};
    border-radius: 10px;
    gridline-color: transparent;
}}
QTableWidget::item {{ padding: 6px 8px; border: none; }}
QTableWidget::item:selected {{ background-color: {ACCENT}; color: #FFFFFF; }}
QHeaderView::section {{
    background-color: {SURFACE};
    color: {GRAY};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 9px 8px;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 1px;
}}

QListWidget#Sidebar {{
    background-color: {BG};
    border: none;
    border-radius: 10px;
}}
QListWidget#Sidebar::item {{
    border-radius: 8px;
    padding: 9px 12px;
    margin: 2px 6px;
    color: {GRAY};
}}
QListWidget#Sidebar::item:hover {{
    background-color: {PANEL2};
    color: {TEXT};
}}
QListWidget#Sidebar::item:selected {{
    background-color: {ACCENT};
    color: #FFFFFF;
    font-weight: 700;
}}
QListWidget {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QListWidget::item {{ padding: 4px 6px; }}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {FAINT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: {FAINT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QProgressBar {{
    background-color: {PANEL2};
    border: 1px solid {BORDER};
    border-radius: 5px;
    height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 4px;
}}

QLabel#PageTitle {{
    font-size: 22px;
    font-weight: 800;
    letter-spacing: 0.5px;
    background: transparent;
}}
QLabel#SectionTitle {{
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 2px;
    color: {GRAY};
    background: transparent;
}}
QLabel#Hint {{
    font-size: 12px;
    color: {GRAY};
    background: transparent;
}}
QLabel#StatCaption {{
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: {GRAY};
}}
QLabel#StatValue {{
    font-size: 26px;
    font-weight: 800;
    color: {TEXT};
    background: transparent;
}}
QLabel#StatDelta {{
    font-size: 12px;
    color: {GRAY};
    background: transparent;
}}
QMenu {{
    background-color: {PANEL2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{ padding: 6px 22px; border-radius: 5px; }}
QMenu::item:selected {{ background-color: {ACCENT}; color: #FFFFFF; }}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 5px 8px;
}}
QToolTip {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 6px;
    border-radius: 4px;
}}
QStatusBar {{
    background: {BG};
    color: {GRAY};
    border-top: 1px solid {BORDER};
}}
QStatusBar::item {{ border: none; }}
"""


# --------------------------------------------------------------------------
# dynamic constant access: `from ui.theme import ACCENT` (and friends) resolves
# against the active palette.
# --------------------------------------------------------------------------
def __getattr__(name: str) -> Any:
    if name == "QSS":
        return build_qss(current_theme())
    if name == "LINE_COLORS":
        return list(current_theme().get("line_colors", DARK["line_colors"]))
    if name in current_theme():
        return current_theme()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# --------------------------------------------------------------------------
# live theme switching
# --------------------------------------------------------------------------
_ALL_COLOR_VALUES = {v for pal in THEMES.values() for v in pal.values() if isinstance(v, str)}


def _is_theme_value(name: str, value: Any) -> bool:
    """True when a module global captured the current theme's value for `name`."""
    if name == "QSS":
        return isinstance(value, str) and any(value == build_qss(pal) for pal in THEMES.values())
    if name == "LINE_COLORS":
        return isinstance(value, list) and any(value == pal.get("line_colors") for pal in THEMES.values())
    return isinstance(value, str) and value in _ALL_COLOR_VALUES


def _active_value(name: str, active: Dict[str, str]) -> Any:
    if name == "QSS":
        return build_qss(active)
    if name == "LINE_COLORS":
        return list(active.get("line_colors", DARK["line_colors"]))
    return active[name]


def refresh_bindings() -> None:
    """Rebind palette colors that modules captured with ``from ui.theme import X``.

    ``from ui.theme import ACCENT`` snapshots the value at import time, so a
    theme change would otherwise leave every already-loaded module stale. This
    walks all imported modules and re-assigns those globals (plus the derived
    ``LINE_COLORS`` / ``QSS``) to the active palette, so the next widget
    rebuild picks up the new colors with no restart.
    """
    import sys  # noqa: PLC0415

    active = current_theme()
    for mod in tuple(sys.modules.values()):
        mod_name = getattr(mod, "__name__", "")
        if mod is None or mod_name == __name__ or mod_name in _SKIP_MODULES:
            continue
        ns = vars(mod)
        for key in _REBIND_KEYS:
            if key in ns and _is_theme_value(key, ns[key]):
                ns[key] = _active_value(key, active)
    _rebuild_derived()


def _rebuild_derived() -> None:
    """Refresh cached structures in other modules that were derived at import time."""
    try:
        import ui.icons as icons_mod  # noqa: PLC0415
    except Exception:  # noqa: BLE001
        return
    icons_mod._ICON_CACHE.clear()
