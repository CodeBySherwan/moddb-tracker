"""TrackerWindow startup wiring smoke test (offscreen Qt).

Guards against the "My Mods / History show nothing on first launch" bug:
manual mods listed in config.json must be registered in the database as soon
as the window is constructed, without waiting for a poll, rescan, or a visit
to the Settings page.
"""

import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    instance.setQuitOnLastWindowClosed(False)
    yield instance


def _fresh_config(tmp_path, mods):
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps(
            {
                "profile_url": "https://www.moddb.com/members/someone",
                "auto_discover": True,
                "mods": mods,
                "paths": {"db": str(tmp_path / "fresh.db")},
                "ui": {"theme": "dark"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return cfg


def test_manual_mods_upserted_at_startup(tmp_path, app):
    cfg = _fresh_config(
        tmp_path,
        ["https://www.moddb.com/mods/alpha", "https://www.moddb.com/addons/beta"],
    )

    # The module-level bootstrap in ui.main_window resolves the theme from
    # --config, so it must be in argv before gui is imported.
    sys.argv = ["pytest", "--config", str(cfg)]
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for mod in ("gui", "ui.main_window"):
        sys.modules.pop(mod, None)

    from gui import TrackerWindow  # noqa: PLC0415

    win = TrackerWindow(str(cfg))
    try:
        mods = win.storage.get_mods(active_only=True)
        assert len(mods) == 2, mods
        name_ids = {m["name_id"] for m in mods}
        assert name_ids == {"alpha", "beta"}, name_ids
        assert win.mods._cards, "My Mods page should render cards immediately"
        assert win.history.mod_combo.count() == 2, "History dropdown should populate"
        for card in win.mods._cards:
            assert not card._pending.isHidden(), "cards without snapshots show 'Not yet polled'"
    finally:
        win.close()


def test_startup_with_empty_mods_stays_empty(tmp_path, app):
    cfg = _fresh_config(tmp_path, [])
    sys.argv = ["pytest", "--config", str(cfg)]
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from gui import TrackerWindow  # noqa: PLC0415

    win = TrackerWindow(str(cfg))
    try:
        assert win.storage.get_mods(active_only=True) == []
        assert win.mods.placeholder.isVisibleTo(win.mods), "placeholder shown when nothing tracked"
        assert "Auto-discovery is on" in win.mods.placeholder.text()
    finally:
        win.close()
