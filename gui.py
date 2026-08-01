"""PyQt6 GUI for the ModDB Tracker.

Entry point: the UI implementation lives in the ``ui`` package
(``ui/pages`` for page widgets, ``ui/main_window`` for the main window and
app flow). This module re-exports the public API and runs the app.

Run with:  python gui.py [--config path/to/config.json]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ui.main_window import FirstRunDialog, TrackerWindow, main, show_window  # noqa: E402
from ui.pages import (  # noqa: E402
    AchievementsPage,
    AnalyticsPage,
    CommentsPage,
    ComparePage,
    DashboardPage,
    EventsPage,
    HistoryPage,
    InsightsPage,
    LogPage,
    ModsPage,
    SearchResultsPage,
    SettingsPage,
)
from ui.pages.settings import is_profile_configured, reset_app_data  # noqa: E402
from ui.widgets import BadgeCard, PlotCard  # noqa: E402

__all__ = [
    "AchievementsPage",
    "AnalyticsPage",
    "BadgeCard",
    "CommentsPage",
    "ComparePage",
    "DashboardPage",
    "EventsPage",
    "FirstRunDialog",
    "HistoryPage",
    "InsightsPage",
    "LogPage",
    "ModsPage",
    "PlotCard",
    "SearchResultsPage",
    "SettingsPage",
    "TrackerWindow",
    "is_profile_configured",
    "main",
    "reset_app_data",
    "show_window",
]

if __name__ == "__main__":
    main()
