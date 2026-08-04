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

MILESTONES = [100, 250, 500, 1_000, 2_500, 5_000, 10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000, 2_500_000, 5_000_000, 10_000_000]


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


def stats_history_series(storage, mod_id: int) -> List[Dict[str, Any]]:
    """Backfilled per-day rows from the ModDB stats page (oldest first)."""
    return [dict(r) for r in storage.stats_history_for(mod_id)]


def stats_history_daily(storage, mod_id: int, key: str = "visits") -> List[Tuple[Date, int]]:
    """(day, per-day count) for one backfilled series, missing days dropped."""
    out: List[Tuple[Date, int]] = []
    for r in storage.stats_history_for(mod_id):
        value = r[key]
        day = _to_date(r["day"])
        if value is not None and day is not None:
            out.append((day, int(value)))
    return out


def stats_history_cumulative(storage, mod_id: int, key: str = "visits") -> List[Tuple[Date, int]]:
    """Cumulative running total for one backfilled series (all days present)."""
    out: List[Tuple[Date, int]] = []
    running = 0
    for r in storage.stats_history_for(mod_id):
        value = r[key]
        if value is not None:
            running += int(value)
        day = _to_date(r["day"])
        if day is not None:
            out.append((day, running))
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
    """Dates when each download threshold was crossed.

    Walks the sorted series directly so a plateau keeps the first date the
    threshold was actually reached.
    """
    out: List[Dict[str, Any]] = []
    for threshold in MILESTONES:
        for day, total in series:
            if total >= threshold:
                out.append({"threshold": threshold, "date": day})
                break
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
    delta_Nd = sum(v for d, v in deltas if (datetime.date.today() - d).days < days)
    growth_pct = round(delta_Nd / start * 100, 1) if start else 0.0
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


def milestone_timeline(storage, mod_id: int) -> Dict[str, Any]:
    """Full-history milestone timeline for one mod: reached milestones (with
    days-between and per-day rate) plus the next milestone with an ETA."""
    series = daily_series(storage, mod_id, days=100 * 365)
    if not series:
        return {"total": 0, "reached": [], "next": None, "first_seen": None, "avg_per_day": 0.0}
    total = series[-1][1]
    first_seen = series[0][0]
    reached: List[Dict[str, Any]] = []
    for m in milestones(series):
        prev_threshold = reached[-1]["threshold"] if reached else 0
        prev_date = reached[-1]["date"] if reached else first_seen
        entry = dict(m)
        days = max(1, (m["date"] - prev_date).days)
        entry["days"] = days
        entry["gain"] = m["threshold"] - prev_threshold
        entry["per_day"] = round(entry["gain"] / days, 1)
        reached.append(entry)

    next_threshold = next((t for t in MILESTONES if total < t), None)
    next_meta: Optional[Dict[str, Any]] = None
    if next_threshold is not None:
        deltas = daily_deltas(series)
        last30 = sum(v for d, v in deltas if (datetime.date.today() - d).days < 30)
        avg = last30 / 30.0
        if avg <= 0:
            avg = total / max(1, (datetime.date.today() - first_seen).days)
        next_meta = {
            "threshold": next_threshold,
            "total": total,
            "remaining": next_threshold - total,
            "avg_per_day": round(avg, 1),
            "eta_days": int(math.ceil((next_threshold - total) / avg)) if avg > 0 else None,
        }
    span = max(1, (datetime.date.today() - first_seen).days)
    return {
        "total": total,
        "reached": reached,
        "next": next_meta,
        "first_seen": first_seen,
        "avg_per_day": round(total / span, 1),
    }


def achievements(storage, mod_id: int) -> Dict[str, Any]:
    """Achievement badges plus the milestone timeline for one mod."""
    tl = milestone_timeline(storage, mod_id)
    s = mod_summary(storage, mod_id, 365)
    totals = {int(t["id"]): t for t in storage.totals_per_mod()}
    comments = int(totals.get(mod_id, {}).get("comments", 0) or 0)

    def _date_of(label: Optional[str]) -> Optional[Date]:
        if not label:
            return None
        try:
            return Date.fromisoformat(str(label).replace("week of ", "")[:10])
        except Exception:  # noqa: BLE001
            return None

    out: List[Dict[str, Any]] = []
    def add(key: str, title: str, detail: str, unlocked: bool, date: Optional[Date] = None) -> None:
        out.append({"key": key, "title": title, "detail": detail, "unlocked": bool(unlocked), "date": date})

    add("tracked", "On the radar", "Mod added to tracking.", True, tl["first_seen"])
    for m in tl["reached"]:
        add(f"milestone-{m['threshold']}", f"{m['threshold']:,} downloads",
            f"Reached on {m['date']} after {m['days']} days ({m['per_day']} per day).", True, m["date"])
    if tl["next"] is not None:
        n = tl["next"]
        eta = f"~{n['eta_days']} days at {n['avg_per_day']}/day" if n["eta_days"] else "pace too slow to tell"
        add(f"milestone-{n['threshold']}", f"{n['threshold']:,} downloads",
            f"{n['total']:,} so far — {n['remaining']:,} to go ({eta}).", False)

    if s["best_week"]:
        add("best-week", "Best week ever", f"{s['best_week']['label']} with +{s['best_week']['value']:,}.", True,
            _date_of(s["best_week"]["label"]))
    deltas = s["deltas"]
    if len(deltas) >= 7 and all(v > 0 for _, v in deltas[-7:]):
        add("steady", "Steady hands", "Positive downloads every day for the last week.", True)
    if s["best_day"]:
        add("big-day", "Big day", f"Best single day: +{s['best_day']['value']:,} on {s['best_day']['label']}.", True,
            _date_of(s["best_day"]["label"]))
    add("community", "Community", f"{comments} comments on this mod.", comments >= 10)
    add("fast-riser", "Fast riser", f"365-day growth of {s['growth_pct']}%.", s["growth_pct"] >= 50)

    return {"milestones": tl, "achievements": out, "summary": s}


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

    # cap contributions per mod so a single big mod can't dominate the strip
    max_per_mod = 2
    per_mod: Dict[str, List[Dict[str, Any]]] = {}
    keep: List[Dict[str, Any]] = []
    for ins in insights:
        mod = ins.get("mod")
        if mod is None:
            keep.append(ins)
            continue
        per_mod.setdefault(mod, []).append(ins)
    for bucket in per_mod.values():
        bucket.sort(key=lambda i: priority.get(i["kind"], 3))
        keep.extend(bucket[:max_per_mod])
    insights = keep

    insights.sort(key=lambda i: priority.get(i["kind"], 3))
    return insights[:limit]


# --------------------------------------------------------------------------
# dashboard helpers (live pyqtgraph data feeds)
# --------------------------------------------------------------------------

def dashboard_downloads_per_day(storage, days: int = 30) -> List[Tuple[Date, int]]:
    """Downloads gained per day, summed across all tracked mods."""
    return storage.daily_download_deltas(days)


def dashboard_total_downloads(storage, days: int = 30) -> List[Tuple[Date, int]]:
    """Cumulative total downloads across all tracked mods, filled per day."""
    deltas = dict(storage.daily_download_deltas(days))
    start = datetime.date.today() - datetime.timedelta(days=days - 1)
    out: List[Tuple[Date, int]] = []
    run = 0
    day = start
    while day <= datetime.date.today():
        run += deltas.get(day, 0)
        out.append((day, run))
        day += datetime.timedelta(days=1)
    return out


def dashboard_mod_overview(storage, days: int = 30, top: int = 5) -> List[Dict[str, Any]]:
    """Summaries for the top-`top` mods (by total downloads), for the overview chart."""
    return all_mods_summary(storage, days)[:top]


def dashboard_comment_activity(storage, days: int = 30) -> List[Tuple[Date, int]]:
    """Comments posted per day across all tracked mods."""
    out: List[Tuple[Date, int]] = []
    for row in storage.comment_counts_per_day(days=days):
        try:
            day = Date.fromisoformat(row["day"])
        except Exception:  # noqa: BLE001
            continue
        out.append((day, int(row["n"] or 0)))
    return out


def comment_activity_split(storage, mod_ids: Optional[List[int]] = None, days: int = 60) -> List[Tuple[Date, int, int]]:
    """(day, comments, replies) per day — replies excluded from the comment count."""
    out: List[Tuple[Date, int, int]] = []
    for r in storage.comment_replies_per_day(mod_ids, days):
        try:
            day = Date.fromisoformat(r["day"])
        except Exception:  # noqa: BLE001
            continue
        out.append((day, int(r["comments"] or 0), int(r["replies"] or 0)))
    return out
