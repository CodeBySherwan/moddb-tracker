"""Regression tests for analytics.py pure functions.

These are the calculations that have already been fixed once (milestone
first-crossing dates, same-window growth_pct) - the suite exists so a future
change to one of these functions can't quietly reintroduce the bug.
"""

import datetime

from analytics import (
    MILESTONES,
    daily_deltas,
    milestones,
    mod_summary,
    moving_average,
    snapshot_daily_deltas,
    weekly_deltas,
)


def _d(start, days):
    return start + datetime.timedelta(days=days)


def test_milestones_first_crossing_survives_plateau():
    base = datetime.date(2025, 1, 1)
    series = [
        (base, 90),
        (_d(base, 1), 95),
        (_d(base, 2), 100),
        (_d(base, 3), 100),
        (_d(base, 4), 100),
    ]
    got = milestones(series)
    assert got[0]["threshold"] == MILESTONES[0]
    assert got[0]["date"] == _d(base, 2)


def test_milestones_reports_only_reached_thresholds():
    series = [(datetime.date(2025, 1, 1), 300)]
    got = {m["threshold"]: m["date"] for m in milestones(series)}
    assert got[MILESTONES[0]] == datetime.date(2025, 1, 1)
    assert got[MILESTONES[1]] == datetime.date(2025, 1, 1)
    assert MILESTONES[2] not in got  # 500 not reached


def test_milestones_empty_series():
    assert milestones([]) == []


def test_daily_deltas_never_negative():
    base = datetime.date(2025, 1, 1)
    series = [(base, 100), (_d(base, 1), 150), (_d(base, 2), 140)]
    assert daily_deltas(series) == [(_d(base, 1), 50), (_d(base, 2), 0)]


def test_daily_deltas_empty_and_single():
    assert daily_deltas([]) == []
    assert daily_deltas([(datetime.date(2025, 1, 1), 10)]) == []


def test_moving_average_trailing_window():
    base = datetime.date(2025, 1, 1)
    series = [(_d(base, i), 10 + i) for i in range(5)]
    ma = moving_average(series, 3)
    assert len(ma) == 5
    assert ma[0][1] == 10.0
    # last window covers indices 2..4 -> (12+13+14)/3
    assert ma[4][1] == 13.0


def test_weekly_deltas_groups_by_week_start():
    monday = datetime.date(2025, 1, 6)  # Monday
    series = [(monday, 100), (_d(monday, 1), 150), (_d(monday, 7), 200)]
    got = dict(weekly_deltas(series))
    assert got[monday] == 50
    assert got[_d(monday, 7)] == 50


def test_snapshot_daily_deltas_derived_from_polls():
    """Addon/file items have no ModDB stats page, so daily counts must come
    from the download totals recorded by each poll."""
    start_day = datetime.date.today() - datetime.timedelta(days=2)
    rows = [
        {"fetched_at": _d(start_day, 0).isoformat(), "downloads_total": 100},
        {"fetched_at": _d(start_day, 1).isoformat(), "downloads_total": 150},
        {"fetched_at": _d(start_day, 2).isoformat(), "downloads_total": 140},
    ]
    got = snapshot_daily_deltas(_FakeSnapshots(rows), 1)
    assert got == [(_d(start_day, 1), 50), (_d(start_day, 2), 0)]


def test_snapshot_daily_deltas_empty():
    assert snapshot_daily_deltas(_FakeSnapshots([]), 1) == []


class _FakeSnapshots:
    """Minimal stand-in for Storage.snapshots_for()."""

    def __init__(self, rows):
        self._rows = rows

    def snapshots_for(self, mod_id):
        return self._rows


def test_mod_summary_growth_pct_over_requested_window():
    start_day = datetime.date.today() - datetime.timedelta(days=29)
    rows = [
        {
            "fetched_at": _d(start_day, i).isoformat(),
            "downloads_total": 1000 + i * 100,
        }
        for i in range(30)
    ]
    s = mod_summary(_FakeSnapshots(rows), 1, days=30)
    assert s["first_total"] == 1000
    assert s["total"] == 3900
    assert s["delta_30d"] == 2900
    assert s["growth_pct"] == 290.0
    assert s["series"][0][0] == start_day
    assert len(s["series"]) == 30
