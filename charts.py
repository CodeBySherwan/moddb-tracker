"""Chart generation for the tracker (matplotlib, dark theme).

All charts are written as PNGs into the configured output directory and can
also be combined into a single dashboard image.
"""

from __future__ import annotations

import datetime
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

ACCENT = "#f0c040"
BLUE = "#29b6f6"
ORANGE = "#ff7043"
PURPLE = "#ab47bc"
GREEN = "#4caf50"
RED = "#ef5350"
GRAY = "#bdbdbd"
PANEL = "#1e1e1e"
GRID = "#333333"

MOD_COLORS = [BLUE, ORANGE, GREEN, PURPLE, ACCENT, RED, "#26a69a", "#ec407a", "#8d6e63"]


def _style(ax) -> None:
    ax.set_facecolor(PANEL)
    ax.grid(color=GRID, linestyle=":", linewidth=0.6, alpha=0.6)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.tick_params(colors=GRAY)
    ax.yaxis.label.set_color(GRAY)
    ax.xaxis.label.set_color(GRAY)


def _fig(**kwargs):
    fig = plt.figure(**kwargs)
    fig.patch.set_facecolor("#111111")
    return fig


def _color_for(index: int) -> str:
    return MOD_COLORS[index % len(MOD_COLORS)]


def per_day_deltas(snapshots_by_mod: Dict[int, List[dict]], mod_names: Dict[int, str], days: int = 45):
    """Compute downloads gained per day (delta between daily maxes) per mod.

    Returns a dict of {mod_name: [(date, delta), ...]} for the last `days` days.
    """
    out: Dict[str, List[tuple]] = {}
    for mod_id, snaps in snapshots_by_mod.items():
        name = mod_names.get(mod_id, f"mod {mod_id}")
        daily_max: Dict[str, int] = {}
        for s in snaps:
            if s.get("downloads_total") is None:
                continue
            try:
                day = datetime.datetime.fromisoformat(s["fetched_at"]).date().isoformat()
            except (ValueError, TypeError):
                continue
            daily_max[day] = max(daily_max.get(day, 0), int(s["downloads_total"]))

        ordered = OrderedDict(sorted(daily_max.items()))
        series = []
        prev_day = None
        prev_total = None
        for day, total in ordered.items():
            if prev_day is not None:
                series.append((prev_day, max(0, total - prev_total)))
            prev_day, prev_total = day, total
        if series:
            out[name] = series[-days:]
    return out


def plot_downloads_per_day(day_deltas: Dict[str, List[tuple]], out_dir: Path) -> Path:
    fig = _fig(figsize=(10, 5))
    ax = fig.add_subplot(111)
    _style(ax)

    x_values: set = set()
    for series in day_deltas.values():
        x_values.update(day for day, _ in series)
    xs = sorted(x_values)

    bar_w = 0.8 / max(1, len(day_deltas))
    for i, (name, series) in enumerate(day_deltas.items()):
        sdict = {day: delta for day, delta in series}
        ys = [sdict.get(day, 0) for day in xs]
        xx = [datetime.date.fromisoformat(day) for day in xs]
        ax.bar(
            [x + datetime.timedelta(days=i * bar_w) for x in xx],
            ys,
            width=bar_w * 0.9,
            color=_color_for(i),
            label=name,
            alpha=0.9,
        )

    ax.set_title("Downloads per day", color=ACCENT, fontweight="bold")
    ax.set_ylabel("Downloads gained")
    if ax.get_legend_handles_labels()[1]:
        ax.legend(facecolor=PANEL, labelcolor=GRAY, edgecolor=GRID)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.autofmt_xdate()
    fig.tight_layout()
    path = out_dir / "downloads_per_day.png"
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def plot_total_downloads(snapshots_by_mod: Dict[int, List[dict]], mod_names: Dict[int, str], out_dir: Path) -> Path:
    fig = _fig(figsize=(10, 5))
    ax = fig.add_subplot(111)
    _style(ax)

    for i, (mod_id, snaps) in enumerate(snapshots_by_mod.items()):
        ts = []
        totals = []
        for s in snaps:
            if s.get("downloads_total") is None:
                continue
            try:
                dt = datetime.datetime.fromisoformat(s["fetched_at"])
            except (ValueError, TypeError):
                continue
            ts.append(dt)
            totals.append(int(s["downloads_total"]))
        if ts:
            ax.plot(ts, totals, color=_color_for(i), label=mod_names.get(mod_id, f"mod {mod_id}"), linewidth=2)
            ax.fill_between(ts, totals, color=_color_for(i), alpha=0.15)

    ax.set_title("Total downloads over time", color=ACCENT, fontweight="bold")
    ax.set_ylabel("Downloads (total)")
    if ax.get_legend_handles_labels()[1]:
        ax.legend(facecolor=PANEL, labelcolor=GRAY, edgecolor=GRID)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.autofmt_xdate()
    fig.tight_layout()
    path = out_dir / "total_downloads.png"
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def plot_mod_overview(totals_per_mod: List[dict], out_dir: Path) -> Path:
    fig = _fig(figsize=(10, 0.55 * max(3, len(totals_per_mod)) + 1.5))
    ax = fig.add_subplot(111)
    _style(ax)

    names = [m["name"] for m in totals_per_mod]
    totals = [m["downloads_total"] for m in totals_per_mod]
    todays = [m["downloads_today"] for m in totals_per_mod]
    y = range(len(names))

    ax.barh(list(y), totals, color=[_color_for(i) for i in range(len(names))], alpha=0.85, label="total")
    ax.barh(list(y), todays, color=ACCENT, alpha=0.95, label="today")
    ax.set_yticks(list(y))
    ax.set_yticklabels(names)
    ax.set_xlabel("Downloads")
    ax.set_title("Mod overview", color=ACCENT, fontweight="bold")
    ax.invert_yaxis()
    ax.legend(facecolor=PANEL, labelcolor=GRAY, edgecolor=GRID)
    fig.tight_layout()
    path = out_dir / "mod_overview.png"
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def plot_comment_activity(comment_counts: List[dict], out_dir: Path) -> Path:
    fig = _fig(figsize=(10, 4))
    ax = fig.add_subplot(111)
    _style(ax)

    days = [datetime.date.fromisoformat(r["day"]) for r in comment_counts]
    counts = [int(r["n"]) for r in comment_counts]
    ax.bar(days, counts, color=GREEN, alpha=0.85, width=0.9)
    ax.set_title("Comments per day", color=ACCENT, fontweight="bold")
    ax.set_ylabel("Comments")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.autofmt_xdate()
    fig.tight_layout()
    path = out_dir / "comment_activity.png"
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def plot_dashboard(
    snapshots_by_mod: Dict[int, List[dict]],
    mod_names: Dict[int, str],
    totals_per_mod: List[dict],
    comment_counts: List[dict],
    out_dir: Path,
) -> Path:
    """Combine the four main views into one 2x2 dashboard PNG."""
    day_deltas = per_day_deltas(snapshots_by_mod, mod_names)

    fig = _fig(figsize=(16, 10))
    axes = [fig.add_subplot(2, 2, i) for i in range(1, 5)]
    for ax in axes:
        _style(ax)

    # 1. downloads per day
    ax = axes[0]
    x_values: set = set()
    for series in day_deltas.values():
        x_values.update(day for day, _ in series)
    xs = sorted(x_values)
    bar_w = 0.8 / max(1, len(day_deltas))
    for i, (name, series) in enumerate(day_deltas.items()):
        sdict = {day: delta for day, delta in series}
        xx = [datetime.date.fromisoformat(day) for day in xs]
        ax.bar(
            [x + datetime.timedelta(days=i * bar_w) for x in xx],
            [sdict.get(day, 0) for day in xs],
            width=bar_w * 0.9,
            color=_color_for(i),
            label=name,
            alpha=0.9,
        )
    ax.set_title("Downloads per day", color=ACCENT, fontweight="bold")

    # 2. total downloads
    ax = axes[1]
    for i, (mod_id, snaps) in enumerate(snapshots_by_mod.items()):
        ts, totals = [], []
        for s in snaps:
            if s.get("downloads_total") is None:
                continue
            try:
                ts.append(datetime.datetime.fromisoformat(s["fetched_at"]))
            except (ValueError, TypeError):
                continue
            totals.append(int(s["downloads_total"]))
        if ts:
            ax.plot(ts, totals, color=_color_for(i), label=mod_names.get(mod_id, "?"), linewidth=2)
    ax.set_title("Total downloads", color=ACCENT, fontweight="bold")

    # 3. mod overview (today vs total)
    ax = axes[2]
    names = [m["name"] for m in totals_per_mod]
    totals = [m["downloads_total"] for m in totals_per_mod]
    todays = [m["downloads_today"] for m in totals_per_mod]
    y = range(len(names))
    ax.barh(list(y), totals, color=[_color_for(i) for i in range(len(names))], alpha=0.85, label="total")
    ax.barh(list(y), todays, color=ACCENT, alpha=0.95, label="today")
    ax.set_yticks(list(y))
    ax.set_yticklabels(names)
    ax.set_title("Mod overview (total vs today)", color=ACCENT, fontweight="bold")
    ax.invert_yaxis()

    # 4. comments per day
    ax = axes[3]
    days = [datetime.date.fromisoformat(r["day"]) for r in comment_counts]
    ax.bar(days, [int(r["n"]) for r in comment_counts], color=GREEN, alpha=0.85, width=0.9)
    ax.set_title("Comments per day", color=ACCENT, fontweight="bold")

    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        if ax.get_legend_handles_labels()[1]:
            ax.legend(facecolor=PANEL, labelcolor=GRAY, edgecolor=GRID, fontsize="small")

    fig.tight_layout()
    path = out_dir / "dashboard.png"
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def generate_all(storage, out_dir: Path) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    mods = storage.get_mods(active_only=True)
    mod_ids = [m["id"] for m in mods]
    mod_names = {m["id"]: m["name"] for m in mods}

    snapshots = {
        mod_id: [dict(s) for s in rows]
        for mod_id, rows in storage.snapshots_for_all(mod_ids).items()
    }
    totals = storage.totals_per_mod()
    comments = [dict(r) for r in storage.comment_counts_per_day(mod_ids)]

    paths = []
    if snapshots:
        paths.append(plot_downloads_per_day(per_day_deltas(snapshots, mod_names), out_dir))
        paths.append(plot_total_downloads(snapshots, mod_names, out_dir))
    if totals:
        paths.append(plot_mod_overview(totals, out_dir))
    if comments:
        paths.append(plot_comment_activity(comments, out_dir))
    if snapshots and totals:
        paths.append(plot_dashboard(snapshots, mod_names, totals, comments, out_dir))

    return paths
