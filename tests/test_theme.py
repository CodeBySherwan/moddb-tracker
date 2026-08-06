"""Theme palettes + live theme switching tests (offscreen Qt).

Guards the "themes only apply after a restart" bug: after a theme change the
app must re-render with the new palette immediately, and every module that
captured colors with ``from ui.theme import X`` must see the new values.
"""

import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import charts  # noqa: E402
import ui.pages.analytics as analytics  # noqa: E402
import ui.pages.comments as comments  # noqa: E402
import ui.pages.dashboard as dashboard  # noqa: E402
import ui.pages.settings as settings_mod  # noqa: E402
import ui.theme as theme  # noqa: E402
from ui.widgets import PlotCard  # noqa: E402

REQUIRED_KEYS = [
    "BG", "CARD", "PANEL", "PANEL2", "SURFACE", "BORDER", "TEXT", "GRAY",
    "FAINT", "ACCENT", "ACCENT_DARK", "SUCCESS", "WARNING", "ERROR", "line_colors",
]


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    instance.setQuitOnLastWindowClosed(False)
    yield instance
    theme.set_theme("dark")
    theme.refresh_bindings()


@pytest.fixture()
def restore_theme():
    saved = theme.current_theme_name()
    yield
    theme.set_theme(saved)
    theme.refresh_bindings()
    instance = QApplication.instance()
    if instance is not None:
        instance.setStyleSheet(theme.build_qss(theme.THEMES[saved]))


def test_themes_have_complete_palettes():
    assert {"nord", "nord-light", "dracula", "solarized-dark", "solarized-light"} <= set(theme.THEMES)
    assert set(theme.DISPLAY_NAMES) == set(theme.THEMES)
    for name, palette in theme.THEMES.items():
        for key in REQUIRED_KEYS:
            assert key in palette, f"{name} is missing {key}"
        assert palette["ACCENT_DARK"] != palette["ACCENT"]
        assert len(palette["line_colors"]) == 8, name


def test_live_switch_rebinds_consumer_globals(restore_theme):
    theme.set_theme("dark")
    theme.refresh_bindings()

    theme.set_theme("nord")
    theme.refresh_bindings()
    pal = theme.current_theme()
    assert dashboard.ACCENT == pal["ACCENT"]
    assert analytics.SUCCESS == pal["SUCCESS"]
    assert comments.LINE_COLORS == list(pal["line_colors"])
    assert comments.ACCENT == pal["ACCENT"]
    assert charts.ACCENT == "#3b82f6", "matplotlib export charts stay dark"


def test_switch_again_to_another_theme(restore_theme):
    theme.set_theme("nord")
    theme.refresh_bindings()
    theme.set_theme("dracula")
    theme.refresh_bindings()
    pal = theme.current_theme()
    assert dashboard.ACCENT == pal["ACCENT"] == "#6272A4"


def test_plotcard_apply_theme_updates_background(app, restore_theme):
    theme.set_theme("dark")
    theme.refresh_bindings()
    card = PlotCard("T", "S")
    try:
        before = card.plot.backgroundBrush().color().name().upper()
        assert before == theme.THEMES["dark"]["CARD"]

        theme.set_theme("nord")
        theme.refresh_bindings()
        card.apply_theme()
        after = card.plot.backgroundBrush().color().name().upper()
        assert after == theme.THEMES["nord"]["CARD"]
        assert after != before
    finally:
        card.deleteLater()


def test_settings_theme_combo_lists_all_themes(app):
    import copy

    import tracker  # noqa: PLC0415

    page = settings_mod.SettingsPage(copy.deepcopy(tracker.DEFAULT_CONFIG))
    try:
        names = [page.theme_combo.itemData(i) for i in range(page.theme_combo.count())]
        assert set(names) == set(theme.THEMES)
    finally:
        page.deleteLater()


def _fresh_config(tmp_path, theme_name):
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps(
            {
                "profile_url": "https://www.moddb.com/members/someone",
                "auto_discover": True,
                "mods": [],
                "poll": {"interval_minutes": 30},
                "paths": {"db": str(tmp_path / "theme.db")},
                "ui": {"theme": theme_name},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return cfg


def test_window_applies_theme_without_restart(tmp_path, app, restore_theme):
    cfg = _fresh_config(tmp_path, "dark")
    sys.argv = ["pytest", "--config", str(cfg)]
    for mod in ("gui", "ui.main_window"):
        sys.modules.pop(mod, None)

    from gui import TrackerWindow  # noqa: PLC0415

    win = TrackerWindow(str(cfg))
    try:
        for name in theme.THEMES:
            cfg.write_text(
                json.dumps(
                    {
                        "profile_url": "https://www.moddb.com/members/someone",
                        "auto_discover": True,
                        "mods": [],
                        "poll": {"interval_minutes": 30},
                        "paths": {"db": str(tmp_path / "theme.db")},
                        "ui": {"theme": name},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            win._on_settings_saved()

            stylesheet = QApplication.instance().styleSheet().lower()
            assert theme.THEMES[name]["BG"].lower() in stylesheet, name
            assert win.settings.theme_combo.currentData() == name, name
            assert theme.current_theme_name() == name
    finally:
        win.close()
