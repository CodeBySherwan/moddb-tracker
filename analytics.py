"""Analytics computations for the ModDB tracker (Phase 2).

Pure functions over :class:`storage.Storage` snapshots: per-mod time series,
growth statistics, milestones and next-week estimates. Used by the interactive
Analytics page and the export reports.
"""

from __future__ import annotations

import datetime
import math
import statistics
from typing import Any, Dict, List, Optional, Tuple

Date = datetime.date

MILESTONES = [100_000, 250_000, 500_000, 1_000_000, 2_500_000, 5_000_000, 10_000_000]


def _to_date(fetched_at: str) -> Optional[Date]:
    try:
        return datetime.date.fromisoformat(str(fetched_at)[:10])
    except Exception:  # noqa: BLE001
        return None


def daily_series(storage, mod_id: int, days: int = 90) -> List[Tuple[Date, int]]:
    """Daily maximum downloads_total per day for one mod, oldest first."""
    daily_max: Dict[Date, int] = {}
    for row in storage.snapshots_for(mod_id):
        day = _to_date(row["fetched_at"])
        if day is None:
            continue
        daily_max[day] = max(daily_max.get(day, 0), int(row["downloads_total"] or 0))
    start = datetime.date.today() - datetime.timedelta(days=days - 1)
    return sorted((d, daily_max[d]) for d in daily_max if d >= start)


def daily_deltas(series: List[Tuple[Date, int]]) -> List[Tuple[Date, int]]:
    """Downloads gained per day (delta between successive daily totals)."""
    out: List[Tuple[Date, int]] = []
    prev: Optional[int] = None
    for day, total in series:
        if prev is not None:
            out.append((day, max(0, total - prev)))
        prev = total
    return out


def moving_average(series: List[Tuple[Date, int]], window: int = 7) -> List[Tuple[Date, float]]:
    """Trailing-window moving average over deltas, padded with None-free head."""
    out: List[Tuple[Date, float]] = []
    values = [v for _, v in series]
    for i in range(len(series)):
        start = max(0, i - window + 1)
        chunk = values[start:i + 1]
        if chunk:
            out.append((series[i][0], round(statistics.fmean(chunk), 1)))
    return out


def daily_totals_range(series: List[Tuple[Date, int]], days: int) -> List[Tuple[Date, int]]:
    """Daily totals filled forward across the last ``days`` days (no gaps)."""
    start = datetime.date.today() - datetime.timedelta(days=days - 1)
    by_day = dict(series)
    out: List[Tuple[Date, int]] = []
    cur = 0
    day = start
    while day <= datetime.date.today():
        cur = by_day.get(day, cur)
        out.append((day, cur))
        day += datetime.timedelta(days=1)
    return out


def aligned_totals(
    series_a: List[Tuple[Date, int]], series_b: List[Tuple[Date, int]], days: int
) -> List[Tuple[Date, int, int]]:
    """(date, total_a, total_b) for every day in the window, both filled forward."""
    start = datetime.date.today() - datetime.timedelta(days=days - 1)
    by_a, by_b = dict(series_a), dict(series_b)
    out: List[Tuple[Date, int, int]] = []
    cur_a = cur_b = 0
    day = start
    while day <= datetime.date.today():
        cur_a = by_a.get(day, cur_a)
        cur_b = by_b.get(day, cur_b)
        out.append((day, cur_a, cur_b))
        day += datetime.timedelta(days=1)
    return out


def weekly_deltas(series: List[Tuple[Date, int]]) -> List[Tuple[Date, int]]:
    """Downloads gained per ISO week, keyed by the week start (Monday)."""
    by_week: Dict[Date, int] = {}
    prev: Optional[int] = None
    for day, total in series:
        if prev is not None and total > prev:
            week_start = day - datetime.timedelta(days=day.weekday())
            by_week[week_start] = by_week.get(week_start, 0) + (total - prev)
        prev = total
    return sorted(by_week.items())


def _best_slice(deltas: List[Tuple[Date, int]], key, fmt) -> Optional[Dict[str, Any]]:
    if not deltas:
        return None
    best = max(deltas, key=key)
    if best[1] <= 0:
        return None
    return {"label": fmt(best[0]), "value": int(best[1])}


def milestones(series: List[Tuple[Date, int]]) -> List[Dict[str, Any]]:
    """Dates when each download threshold was crossed."""
    out: List[Dict[str, Any]] = []
    by_value = {total: day for day, total in series}
    totals = sorted(by_value)
    for threshold in MILESTONES:
        if totals and totals[-1] >= threshold:
            idx = next((i for i, t in enumerate(totals) if t >= threshold), None)
            if idx is not None:
                out.append({"threshold": threshold, "date": by_value[totals[idx]]})
    return out


def estimate_next_week(series: List[Tuple[Date, int]], days_ahead: int = 7) -> Optional[int]:
    """Linear regression over the last 14 daily totals, extrapolated ahead."""
    if len(series) < 3:
        return None
    origin = series[0][0]
    recent = series[-14:]
    xs = [(d - origin).days for d, _ in recent]
    ys = [v for _, v in recent]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        slope = 0.0
    else:
        slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom
    intercept = mean_y - slope * mean_x
    latest = ys[-1]
    estimate = intercept + slope * (xs[-1] + days_ahead)
    return max(0, int(round(estimate - latest)))


def mod_summary(storage, mod_id: int, days: int = 90) -> Dict[str, Any]:
    """Everything the Analytics page shows for a single mod."""
    series = daily_series(storage, mod_id, days)
    deltas = daily_deltas(series)
    ma7 = moving_average(deltas, 7)
    weeks = weekly_deltas(series)
    total = series[-1][1] if series else 0
    start = series[0][1] if series else 0
    delta_7d = sum(v for d, v in deltas if (datetime.date.today() - d).days < 7)
    delta_30d = sum(v for d, v in deltas if (datetime.date.today() - d).days < 30)
    growth_pct = round(delta_30d / start * 100, 1) if start else 0.0
    avg_per_day = round(delta_30d / 30, 1) if deltas else 0.0
    best_day = _best_slice(deltas, lambda p: p[1], lambda d: d.isoformat())
    best_week = _best_slice(weeks, lambda p: p[1], lambda d: f"week of {d.isoformat()}")
    next_week = estimate_next_week(series, 7)
    return {
        "mod_id": mod_id,
        "total": total,
        "first_total": start,
        "first_seen": series[0][0] if series else None,
        "delta_7d": delta_7d,
        "delta_30d": delta_30d,
        "growth_pct": growth_pct,
        "avg_per_day": avg_per_day,
        "best_day": best_day,
        "best_week": best_week,
        "milestones": milestones(series),
        "next_week_estimate": next_week,
        "series": series,
        "deltas": deltas,
        "ma7": ma7,
        "weeks": weeks,
        "days": days,
    }


def all_mods_summary(storage, days: int = 90) -> List[Dict[str, Any]]:
    """Summaries for every active tracked mod, sorted by total downloads desc."""
    totals = {int(t["id"]): t for t in storage.totals_per_mod()}
    out = []
    for mod in storage.get_mods(active_only=True):
        mid = int(mod["id"])
        s = mod_summary(storage, mid, days)
        s["name"] = mod["name"]
        s["name_id"] = mod["name_id"]
        s["url"] = mod["url"]
        s["content_type"] = mod["content_type"]
        s["favorite"] = bool(mod["favorite"])
        t = totals.get(mid, {})
        s["watchers"] = t.get("watchers")
        s["comments"] = t.get("comments", 0)
        out.append(s)
    out.sort(key=lambda s: s["total"], reverse=True)
    return out


def aggregate_summary(summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summed stats across all tracked mods."""
    total = sum(s["total"] for s in summaries)
    delta_7d = sum(s["delta_7d"] for s in summaries)
    delta_30d = sum(s["delta_30d"] for s in summaries)
    next_week = sum(s["next_week_estimate"] or 0 for s in summaries)
    return {
        "total": total,
        "delta_7d": delta_7d,
        "delta_30d": delta_30d,
        "next_week": next_week,
        "count": len(summaries),
    }


def _mk_insight(kind: str, title: str, detail: str, mod: Optional[str] = None) -> Dict[str, Any]:
    return {"kind": kind, "title": title, "detail": detail, "mod": mod}


def generate_insights(storage, days: int = 30, limit: int = 14) -> List[Dict[str, Any]]:
    """Rule-based insight lines ("downloads up 37% vs last week"). No LLM used."""
    summaries = all_mods_summary(storage, days)
    today = datetime.date.today()
    week_ago = today - datetime.timedelta(days=7)
    insights: List[Dict[str, Any]] = []

    for s in summaries:
        name = s["name"]
        d7 = s["delta_7d"]
        d30 = s["delta_30d"]
        avg_day = d30 / 30.0
        deltas = s["deltas"]

        if len(deltas) >= 7 and avg_day > 0 and d7 >= 0:
            avg_7 = d7 / 7.0
            ratio = avg_7 / avg_day
            if ratio >= 1.5:
                pct = round((ratio - 1) * 100)
                insights.append(_mk_insight(
                    "positive", f"{name}: momentum",
                    f"Downloads are running {pct}% above your 30-day average over the last week "
                    f"(+{d7:,} vs avg {avg_day:,.0f}/day).",
                    name))
            elif ratio <= 0.6:
                pct = round((1 - ratio) * 100)
                insights.append(_mk_insight(
                    "negative", f"{name}: slowing down",
                    f"Last week's gains are {pct}% below your 30-day average "
                    f"(+{d7:,} vs avg {avg_day:,.0f}/day).", name))

        for m in s["milestones"]:
            if m["date"] >= week_ago:
                insights.append(_mk_insight(
                    "positive", f"{name} hit a milestone",
                    f"Crossed {m['threshold']:,} downloads on {m['date']} — total now {s['total']:,}.", name))

        bw = s["best_week"]
        if bw and len(deltas) >= 14:
            try:
                bw_date = datetime.date.fromisoformat(bw["label"].replace("week of ", ""))
            except Exception:  # noqa: BLE001
                bw_date = None
            if bw_date and bw_date >= week_ago and d7 >= bw["value"] * 0.8:
                insights.append(_mk_insight(
                    "positive", f"{name}: best week ever",
                    f"Last week (+{d7:,}) is your best week on record for this mod.", name))

        next_threshold = next((t for t in MILESTONES if s["total"] < t), None)
        if next_threshold and avg_day > 0 and (next_threshold - s["total"]) <= s["total"] * 0.10:
            eta = int(math.ceil((next_threshold - s["total"]) / avg_day))
            insights.append(_mk_insight(
                "info", f"{name}: milestone in sight",
                f"About {eta} days from {next_threshold:,} downloads at the current pace.", name))

        if len(deltas) >= 7 and all(v[1] > 0 for v in deltas[-7:]) and d7 > 0:
            insights.append(_mk_insight(
                "info", f"{name}: steady growth",
                "Positive downloads every day for the last week.", name))

        if d30 <= 0 and s["total"] > 0:
            insights.append(_mk_insight(
                "negative", f"{name}: flat",
                "No download growth over the last 30 days.", name))

    if summaries:
        agg = aggregate_summary(summaries)
        insights.append(_mk_insight(
            "info", "All tracked mods",
            f"{agg['count']} mods, {agg['total']:,} downloads, +{agg['delta_7d']:,} in 7 days, "
            f"~{agg['next_week']:,} projected next week."))
        fastest = max(summaries, key=lambda s: s["delta_7d"])
        if fastest["delta_7d"] > 0:
            insights.append(_mk_insight(
                "positive", "Fastest-growing mod",
                f"{fastest['name']} gained +{fastest['delta_7d']:,} downloads in the last 7 days.", fastest["name"]))

    priority = {"positive": 0, "info": 1, "negative": 2}
    insights.sort(key=lambda i: priority.get(i["kind"], 3))
    return insights[:limit]
