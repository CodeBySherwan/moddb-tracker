"""History page data tests (offscreen Qt).

Guards the fix for the "always empty" History charts: daily counts fall back
to poll-derived download deltas when ModDB has no per-day stats page (addons /
files), and the snapshot chart shows downloads-over-time instead of rank.
"""

import datetime
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.pages.history import HistoryPage  # noqa: E402


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    instance.setQuitOnLastWindowClosed(False)
    yield instance


def _seed(db, content_type="addon", with_stats_history=False):
    mod_id = db.upsert_mod("test-item", "https://www.moddb.com/mods/x/addons/test-item", "Test Item", content_type)
    start = datetime.date.today() - datetime.timedelta(days=2)
    for i in range(3):
        db.conn.execute(
            "INSERT INTO snapshots(mod_id, fetched_at, downloads_total, downloads_today, visits, "
            "visits_today, rank, rank_total, watchers, rating) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                mod_id,
                f"{start + datetime.timedelta(days=i)}T12:00:00",
                100 + i * 50,
                10,
                500 + i * 10,
                5,
                None,
                None,
                0,
                None,
            ),
        )
    db.conn.commit()
    if with_stats_history:
        db.replace_stats_history(mod_id, [
            {"day": (start + datetime.timedelta(days=i)).isoformat(), "visits": 10, "downloads": 2}
            for i in range(3)
        ])
    return mod_id


def test_snapshot_daily_counts_show_for_addon(db, app):
    mod_id = _seed(db, content_type="addon")
    page = HistoryPage()
    page.refresh(db)
    try:
        assert not page.backfill_btn.isVisibleTo(page), "backfill is mod-only"
        names = {e["name"] for e in page.plot_full._series}
        assert names == {"Downloads per day", "Total"}, names
        # 3 snapshot days -> 3 table rows
        assert page.stats_table.rowCount() == 3
        assert "addons/files" in page.coverage.text()
        snap_names = {e["name"] for e in page.plot_downloads._series}
        assert snap_names == {"Downloads"}, snap_names
    finally:
        page.close()


def test_backfilled_stats_history_used_for_mods(db, app):
    mod_id = _seed(db, content_type="mod", with_stats_history=True)
    page = HistoryPage()
    page.refresh(db)
    try:
        assert page.backfill_btn.isVisibleTo(page), "backfill visible for mods"
        names = {e["name"] for e in page.plot_full._series}
        assert names == {"Visits", "Downloads"}, names
        assert "Backfilled: 3 day(s)" in page.coverage.text()
        assert page.stats_table.rowCount() == 3
    finally:
        page.close()


def test_empty_state_message_when_no_snapshots(db, app):
    db.upsert_mod("fresh", "https://www.moddb.com/mods/x/fresh", "Fresh", "addon")
    page = HistoryPage()
    page.refresh(db)
    try:
        assert page.plot_full._series == []
        assert page.stats_table.rowCount() == 0
        assert page.plot_downloads._series == []
    finally:
        page.close()
