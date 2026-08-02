"""ModDB Tracker -- track downloads, today's downloads, comments and replies
for your ModDB mods, with charts and Windows toast notifications.

Usage
-----
    python tracker.py --init                 first run: discover mods, baseline, charts
    python tracker.py --poll                 one poll cycle (run me from Task Scheduler)
    python tracker.py --report               print current stats
    python tracker.py --charts               regenerate chart images
    python tracker.py --discover             refresh the mod list from your profile
    python tracker.py --install-scheduler    create the Task Scheduler job
    python tracker.py --remove-scheduler     delete the Task Scheduler job
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import re
import subprocess
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import transport
from storage import Storage

try:
    import moddb
except ImportError as exc:  # pragma: no cover
    sys.stderr.write("Missing dependency. Run: pip install -r requirements.txt\n")
    sys.exit(1)

CONFIG_FILE = "config.json"
DEFAULT_CONFIG: Dict[str, Any] = {
    "profile_url": "https://www.moddb.com/members/YOUR-USERNAME",
    "auto_discover": True,
    "mods": [],
    "poll": {
        "interval_minutes": 30,
        "notify_on_downloads": True,
        "notify_on_comments": True,
        "notify_on_replies": True,
        "charts_each_poll": True,
    },
    "notifications": {
        "app_id": "ModDB Tracker",
        "max_toasts": 5,
    },
    "tray": {
        "minimize_to_tray": True,
        "start_minimized": False,
    },
    "paths": {
        "db": "tracker.db",
        "output": "output",
        "logs": "logs",
    },
    "ui": {
        "fullscreen": True,
        "poll_on_open": True,
        "theme": "dark",
        "mods_sort": 0,
        "mods_filter": "",
        "analytics_days": 60,
        "dashboard": {
            "stats": True,
            "insights": True,
            "charts": True,
            "activity": True,
            "activity_position": "right",
        },
    },
}

logger = logging.getLogger("tracker")

HEADERS = {"Downloads": "downloads_total", "Today": "downloads_today", "Visits": "visits",
           "Visits today": "visits_today", "Watchers": "watchers", "Rating": "rating",
           "Rank": "rank", "Files": "files"}


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------

def load_config(config_path: str = CONFIG_FILE) -> Dict[str, Any]:
    def _merge(base: dict, override: dict) -> dict:
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                _merge(base[key], value)
            else:
                base[key] = value
        return base

    path = Path(config_path)
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if path.exists():
        user = json.loads(path.read_text(encoding="utf-8"))
        cfg = _merge(cfg, user)
    return cfg


def save_config(config: Dict[str, Any], config_path: str = CONFIG_FILE) -> None:
    Path(config_path).write_text(json.dumps(config, indent=2), encoding="utf-8")


def setup_logging(config: Dict[str, Any]) -> None:
    log_dir = Path(config["paths"]["logs"])
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    info_handler = RotatingFileHandler(log_dir / "tracker.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    info_handler.setFormatter(fmt)
    root.addHandler(info_handler)

    err_handler = RotatingFileHandler(log_dir / "error.log", maxBytes=500_000, backupCount=2, encoding="utf-8")
    err_handler.setLevel(logging.ERROR)
    err_handler.setFormatter(fmt)
    root.addHandler(err_handler)

    # quiet the moddb package logger
    logging.getLogger("moddb").setLevel(logging.WARNING)
    # quiet curl_cffi's noisy debug logging if any
    logging.getLogger("curl_cffi").setLevel(logging.WARNING)


# --------------------------------------------------------------------------
# ModDB fetching
# --------------------------------------------------------------------------

def parse_downloads_stats(html) -> Dict[str, Any]:
    """Parse the 'File Statistics' box from a mod/addon /downloads page."""
    stats: Dict[str, Any] = {}
    box = html.find("div", id="downloadsstats")
    if not box:
        return stats
    for row in box.find_all("div", class_="row clear"):
        h5 = row.find("h5")
        summary = row.find("span", class_="summary")
        if not h5 or not summary:
            continue
        key = h5.get_text(strip=True).lower().replace(" ", "_")
        text = summary.get_text(strip=True).replace(",", "")
        if key in ("downloads", "downloads_today", "files"):
            try:
                stats[key] = int(text)
            except ValueError:
                stats[key] = 0
        else:
            stats[key] = text
    return stats


STATS_SERIES_KEYS = {
    "Visitors": "visits",
    "Downloads": "downloads",
    "Videos": "videos",
    "Images": "images",
    "Articles": "articles",
}


def parse_stats_history(html_text: str) -> Dict[str, List[Tuple[str, int]]]:
    """Extract the per-day series embedded in a ModDB ``/stats`` page.

    The chart is rendered from a JSON blob inside
    ``AmCharts.makeChart("chartdivmod", {...})``; each dataset is a list of
    ``{"date": "YYYY-MM-DD", "total": "N"}`` per-day counters.
    """
    match = re.search(r'AmCharts\.makeChart\(\s*"chartdivmod"\s*,\s*(\{)', html_text)
    if not match:
        return {}
    start = match.start(1)
    depth = 0
    end = None
    for i in range(start, len(html_text)):
        ch = html_text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return {}
    raw = html_text[start:end]
    try:
        cfg = json.loads(raw)
    except ValueError:
        cfg = json.loads(re.sub(r",\s*([}\]])", r"\1", raw))

    out: Dict[str, List[Tuple[str, int]]] = {}
    for ds in cfg.get("dataSets", []):
        key = STATS_SERIES_KEYS.get(ds.get("title", ""))
        if key is None:
            continue
        series: List[Tuple[str, int]] = []
        for point in ds.get("dataProvider", []):
            try:
                series.append((point["date"], int(point["total"])))
            except (KeyError, TypeError, ValueError):
                continue
        out[key] = series
    return out


def fetch_stats_history(url: str) -> Dict[str, List[Tuple[str, int]]]:
    """Fetch and parse the public stats page for an item (``<url>/stats``)."""
    return parse_stats_history(transport.get_raw(f"{url.rstrip('/')}/stats"))


def backfill_stats_history(storage: Storage, mod: Dict[str, Any]) -> Dict[str, Any]:
    """Backfill the per-day stats history for one mod from its stats page."""
    series = fetch_stats_history(mod["url"])
    by_day: Dict[str, Dict[str, Any]] = {}
    for key, points in series.items():
        for day, value in points:
            by_day.setdefault(day, {"day": day})[key] = value
    rows = [by_day[d] for d in sorted(by_day)]
    storage.replace_stats_history(mod["id"], rows)
    coverage = storage.stats_history_coverage(mod["id"])
    coverage["series"] = {key: len(points) for key, points in series.items()}
    logger.info(
        "Backfilled %s: %d day(s) from %s to %s",
        mod["name"],
        coverage["days"],
        coverage["first"],
        coverage["last"],
    )
    return coverage


def backfill_all_stats_history(storage: Storage, config: Dict[str, Any]) -> str:
    """Backfill stats history for every active tracked mod."""
    mods = storage.get_mods(active_only=True)
    if not mods:
        return "No tracked mods."
    lines: List[str] = []
    for mod in mods:
        target = dict(mod)
        try:
            coverage = backfill_stats_history(storage, target)
            lines.append(f"{target['name']}: {coverage['days']} day(s)")
        except Exception as exc:  # noqa: BLE001
            logger.error("Backfill failed for %s: %s", target["name"], exc)
            lines.append(f"{target['name']}: failed ({exc})")
    return "\n".join(lines)


def page_type_for(url: str) -> str:
    if "/addons/" in url:
        return "addon"
    if "/mods/" in url and "/downloads/" not in url:
        return "mod"
    return "file"


def classify_url(url: str) -> str:
    if "/addons/" in url:
        return "addon"
    if "/mods/" in url:
        return "mod"
    return "file"


def parse_member_rows(html) -> List[Tuple[str, str, str]]:
    """Parse the rowcontent items on a member tab page (mods / addons / downloads)."""
    out: List[Tuple[str, str, str]] = []
    for row in html.find_all("div", class_="rowcontent"):
        img = row.find("a", class_="image")
        h4 = row.find("h4")
        a = h4.find("a") if h4 else None
        name = (a.get_text(strip=True) if a else (img.get("title") if img else ""))
        href = (a.get("href") if a else (img.get("href") if img else None))
        if not href:
            continue
        url = "https://www.moddb.com" + href if href.startswith("/") else href
        out.append((name or url.rstrip("/").split("/")[-1], url, classify_url(url)))
    return out


def fetch_mod_snapshot(url: str, content_type: str = "mod") -> Tuple[Dict[str, Any], Any]:
    """Fetch a mod / addon / file page.

    Returns (snapshot_fields, page_object). Never raises for a single item:
    failures are logged and a minimal dict is returned.
    """
    fields: Dict[str, Any] = {}
    mod_obj = None

    try:
        html = transport.get_page(url)
        if content_type == "mod":
            mod_obj = moddb.Mod(html)
            fields["downloads_total"] = getattr(mod_obj.profile, "download_count", 0) or 0
            if mod_obj.stats:
                fields["visits"] = getattr(mod_obj.stats, "visits", 0) or 0
                fields["visits_today"] = getattr(mod_obj.stats, "today", 0) or 0
                fields["rank"] = getattr(mod_obj.stats, "rank", None)
                fields["rank_total"] = getattr(mod_obj.stats, "total", None)
                fields["watchers"] = getattr(mod_obj.stats, "watchers", None)
                fields["files"] = getattr(mod_obj.stats, "files", None)
            fields["rating"] = getattr(mod_obj, "rating", None)
        else:
            # addon and standalone files share the File model
            mod_obj = moddb.Addon(html) if content_type == "addon" else moddb.File(html)
            fields["downloads_total"] = getattr(mod_obj, "downloads", 0) or 0
            fields["downloads_today"] = getattr(mod_obj, "today", 0) or 0
            fields["rating"] = None
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to parse page %s: %s", url, exc)

    # the mod's /downloads tab gives the authoritative file download counters
    if content_type == "mod":
        try:
            dl_html = transport.get_page(f"{url}/downloads")
            dl_stats = parse_downloads_stats(dl_html)
            if "downloads" in dl_stats:
                fields["downloads_total"] = dl_stats["downloads"]
            if "downloads_today" in dl_stats:
                fields["downloads_today"] = dl_stats["downloads_today"]
            if "files" in dl_stats:
                fields["files"] = dl_stats["files"]
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to parse downloads page for %s: %s", url, exc)

    fields.setdefault("downloads_today", 0)
    return fields, mod_obj


def iter_comments_with_parent(comment_list):
    """Yield (comment, parent_comment_or_None) following the 2-level nesting."""
    for top in comment_list:
        yield top, None
        for child in top.children:
            yield child, top
            for grand in child.children:
                yield grand, child


def fetch_new_comments(mod_obj, mod_id: int, storage: Storage, fetch_pages: int = 2) -> List[Dict[str, Any]]:
    """Return dicts for comments not yet stored.

    `fetch_pages`: 1 -> first page only; 2 -> first page + last page (default,
    catches the newest comments, which ModDB appends at the end).
    """
    new_comments: List[Dict[str, Any]] = []
    if mod_obj is None:
        return new_comments

    try:
        first = mod_obj.get_comments(1)
        pages = [first]
        if fetch_pages >= 2 and first.total_pages > 1:
            pages.append(first.to_page(first.total_pages))

        for page in pages:
            for comment, parent in iter_comments_with_parent(page):
                if comment.id is None:  # MissingComment placeholder
                    continue
                if storage.comment_exists(comment.id):
                    continue

                author = getattr(comment.author, "name", None) or "unknown"
                parent_id = parent.id if parent is not None else None
                posted = comment.date.isoformat() if comment.date else None
                storage.add_comment(
                    comment_id=comment.id,
                    mod_id=mod_id,
                    author=author,
                    content=comment.content,
                    posted_at=posted,
                    position=comment.position,
                    parent_id=parent_id,
                    author_url=getattr(comment.author, "url", None),
                )
                new_comments.append(
                    {
                        "id": comment.id,
                        "author": author,
                        "content": comment.content or "",
                        "parent_author": parent.author.name if (parent is not None and parent.author) else None,
                        "position": comment.position,
                    }
                )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to fetch comments for %s: %s", getattr(mod_obj, "url", "?"), exc)

    return new_comments


# --------------------------------------------------------------------------
# discovery
# --------------------------------------------------------------------------

def discover_mods(storage: Storage, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    profile_url = config["profile_url"]
    found: List[Dict[str, Any]] = []

    if config.get("auto_discover"):
        try:
            member = moddb.parse_page(profile_url)
            storage.meta_set("member_name", getattr(member, "name", ""))
            storage.meta_set("member_name_id", getattr(member, "name_id", ""))

            seen: Dict[str, bool] = {}
            member_url = getattr(member, "url", profile_url.rstrip("/"))
            for tab in ("mods", "addons", "downloads"):
                try:
                    tab_html = transport.get_page(f"{member_url}/{tab}")
                    for name, url, content_type in parse_member_rows(tab_html):
                        if url in seen:
                            continue
                        seen[url] = True
                        name_id = url.rstrip("/").split("/")[-1]
                        mod_id = storage.upsert_mod(name_id, url, name, content_type)
                        found.append(
                            {"id": mod_id, "name_id": name_id, "url": url, "name": name, "content_type": content_type}
                        )
                        logger.info("Discovered %s: %s (%s)", content_type, name, url)
                except Exception as exc:  # noqa: BLE001
                    logger.error("Failed to scan member %s tab: %s", tab, exc)
        except Exception as exc:  # noqa: BLE001
            logger.error("Mod discovery failed for %s: %s", profile_url, exc)

    # manual mods from config, added as well
    for url in config.get("mods", []):
        if not url:
            continue
        name_id = url.rstrip("/").split("/")[-1]
        content_type = classify_url(url)
        try:
            html = transport.get_page(url)
            obj = moddb.Mod(html) if content_type == "mod" else (
                moddb.Addon(html) if content_type == "addon" else moddb.File(html)
            )
            name = getattr(obj, "name", name_id)
        except Exception:  # noqa: BLE001
            name = name_id
        mod_id = storage.upsert_mod(name_id, url, name, content_type)
        found.append({"id": mod_id, "name_id": name_id, "url": url, "name": name, "content_type": content_type})

    if not found:
        logger.warning("No mods found. Set auto_discover=true and your profile_url, or list mods in config['mods'].")

    return found


# --------------------------------------------------------------------------
# poll / init
# --------------------------------------------------------------------------

def member_names(storage: Storage) -> List[str]:
    names = set()
    for key in ("member_name", "member_name_id"):
        val = storage.meta_get(key)
        if val:
            names.add(val.strip().lower())
    return sorted(n for n in names if n)


def classify_comment(comment: Dict[str, Any], member_names: List[str]) -> str:
    if comment["parent_author"] and comment["parent_author"].lower() in member_names:
        return "reply"
    # Demoted fallback: only trust a username mention when the structural
    # signal is unavailable (parent comment author unknown/blank), so a
    # top-level comment like "thanks <name>, great mod!" isn't miscounted
    # as a reply.
    if not comment["parent_author"]:
        content = (comment["content"] or "").lower()
        for name in member_names:
            if name and name in content:
                return "reply"
    return "comment"


def snapshot_mod(storage: Storage, mod: Dict[str, Any], config: Dict[str, Any], notify: bool) -> List[Dict[str, Any]]:
    """Fetch one mod, store a snapshot, detect new comments.

    Returns a list of notification dicts (title/message/url).
    """
    events: List[Dict[str, Any]] = []
    mod_id = mod["id"]
    mod_name = mod["name"]
    mod_url = mod["url"]

    fields, mod_obj = fetch_mod_snapshot(mod_url, content_type=mod.get("content_type", "mod"))
    if not fields:
        logger.error("No data retrieved for %s -- skipping", mod_name)
        return events

    last = storage.last_snapshot(mod_id)
    storage.add_snapshot(mod_id, **fields)

    delta = 0
    if last is not None and last["downloads_total"] is not None:
        delta = max(0, int(fields["downloads_total"]) - int(last["downloads_total"]))

    downloads_today = int(fields.get("downloads_today") or 0)
    downloads_total = int(fields.get("downloads_total") or 0)

    if delta > 0:
        storage.add_event(
            "download",
            f"+{delta} new download{'s' if delta != 1 else ''} (total {downloads_total:,})",
            mod_id,
            mod_name,
            mod_url,
        )

    if notify and config["poll"]["notify_on_downloads"]:
        if delta > 0:
            events.append(
                {
                    "title": "ModDB Tracker",
                    "message": f"{mod_name}: +{delta} new download{'s' if delta != 1 else ''} "
                               f"(total {downloads_total:,})",
                    "url": mod_url,
                }
            )
        elif downloads_today > 0 and storage.meta_get(f"dl_notified_{mod_id}_{datetime.date.today().isoformat()}") is None:
            # once-daily summary for the first check where today's count is visible
            events.append(
                {
                    "title": "ModDB Tracker",
                    "message": f"{mod_name}: {downloads_today} download{'s' if downloads_today != 1 else ''} today "
                               f"(total {downloads_total:,})",
                    "url": mod_url,
                }
            )
            storage.meta_set(f"dl_notified_{mod_id}_{datetime.date.today().isoformat()}", "1")

    new_comments = fetch_new_comments(
        mod_obj,
        mod_id,
        storage,
        fetch_pages=2,
    )

    m_names = member_names(storage)
    for comment in new_comments:
        if comment["author"].lower() in m_names:
            continue  # our own comment
        kind = classify_comment(comment, m_names)
        snippet = (comment["content"] or "")[:160].replace("\n", " ")
        storage.add_event(
            kind,  # "reply" or "comment"
            f"{comment['author']}: {snippet}",
            mod_id,
            mod_name,
            mod_url,
        )
        if not notify:
            continue
        if kind == "reply":
            if config["poll"]["notify_on_replies"]:
                events.append(
                    {
                        "title": f"New reply on {mod_name}",
                        "message": f"{comment['author']}: {snippet}",
                        "url": mod_url,
                    }
                )
        else:
            if config["poll"]["notify_on_comments"]:
                events.append(
                    {
                        "title": f"New comment on {mod_name}",
                        "message": f"{comment['author']}: {snippet}",
                        "url": mod_url,
                    }
                )

    logger.info(
        "Polled %s: total=%s today=%s delta=%s new_comments=%s",
        mod_name,
        downloads_total,
        downloads_today,
        delta,
        len(new_comments),
    )
    return events


def run_poll(storage: Storage, config: Dict[str, Any], notify: bool = True) -> int:
    mods = storage.get_mods(active_only=True)
    if not mods:
        logger.warning("No tracked mods. Run --init first or add mods to config.")
        return 1

    all_events: List[Dict[str, Any]] = []
    for mod in mods:
        events = snapshot_mod(storage, dict(mod), config, notify=notify)
        all_events.extend(events)

    if notify:
        try:
            import notify as notif
            notif.notify_events(all_events, config)
        except Exception as exc:  # noqa: BLE001 - toasts are optional; never crash a poll
            logger.warning("Toast notifications unavailable (%s): %s", type(exc).__name__, exc)
        if config["poll"]["charts_each_poll"]:
            try:
                import charts
                charts.generate_all(storage, Path(config["paths"]["output"]))
                logger.info("Charts regenerated")
            except Exception as exc:  # noqa: BLE001
                logger.error("Chart generation failed: %s", exc)

    storage.meta_set("last_poll", datetime.datetime.now().isoformat(timespec="seconds"))
    return 0


def run_init(storage: Storage, config: Dict[str, Any]) -> int:
    mods = discover_mods(storage, config)
    if not mods:
        logger.error("Nothing to track. Check profile_url in %s", CONFIG_FILE)
        return 1

    logger.info("Initialising baseline for %d mod(s)...", len(mods))
    for mod in mods:
        snapshot_mod(storage, mod, config, notify=False)  # baseline, no notifications

    try:
        import charts
        charts.generate_all(storage, Path(config["paths"]["output"]))
        logger.info("Charts written to %s", config["paths"]["output"])
    except Exception as exc:  # noqa: BLE001
        logger.error("Chart generation failed: %s", exc)

    storage.meta_set("initialised", datetime.datetime.now().isoformat(timespec="seconds"))
    return 0


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def run_report(storage: Storage, config: Dict[str, Any]) -> int:
    mods = storage.get_mods(active_only=True)
    if not mods:
        logger.warning("No tracked mods.")
        return 1

    totals = storage.totals_per_mod()
    width = max([len(m["name"]) for m in totals] + [10])
    print("")
    print(f"{'Mod':<{width}} {'Downloads':>10} {'Today':>6} {'Visits':>9} {'V.today':>7} {'Watch':>5} {'Rank':>8}")
    print("-" * (width + 60))
    for m in totals:
        rank = f"{m['rank'] or '-'}/{m['rank_total'] or '-'}"
        print(
            f"{m['name']:<{width}} {m['downloads_total']:>10,} {m['downloads_today']:>6,} "
            f"{m['visits']:>9,} {m['visits_today']:>7,} {m['watchers'] or 0:>5} {rank:>8}"
        )
    print("")

    last_poll = storage.meta_get("last_poll")
    if last_poll:
        print(f"Last poll: {last_poll}")
    return 0


# --------------------------------------------------------------------------
# Task Scheduler
# --------------------------------------------------------------------------

def task_command(config: Dict[str, Any]) -> str:
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    tracker = Path(__file__).resolve()
    cfg = Path(CONFIG_FILE).resolve()
    return f'"{pythonw}" "{tracker}" --poll --config "{cfg}"'


def install_scheduler(config: Dict[str, Any]) -> int:
    interval = max(1, int(config["poll"]["interval_minutes"]))
    cmd = task_command(config)
    res = subprocess.run(
        [
            "schtasks",
            "/Create",
            "/F",
            "/TN", "ModDBTracker",
            "/TR", cmd,
            "/SC", "MINUTE",
            "/MO", str(interval),
            "/ST", "09:00",
        ],
        capture_output=True,
        text=True,
    )
    print(res.stdout or res.stderr)
    if res.returncode == 0:
        print(f"Task 'ModDBTracker' installed (every {interval} min). Command: {cmd}")
        print("Note: keep your PC on and logged in for toasts to appear.")
    return res.returncode


def remove_scheduler() -> int:
    res = subprocess.run(["schtasks", "/Delete", "/F", "/TN", "ModDBTracker"], capture_output=True, text=True)
    print(res.stdout or res.stderr)
    return res.returncode


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="ModDB mod tracker")
    parser.add_argument("--config", default=CONFIG_FILE, help="path to config.json")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--init", action="store_true", help="first run: discover, baseline, charts")
    mode.add_argument("--poll", action="store_true", help="run one poll cycle")
    mode.add_argument("--report", action="store_true", help="print a stats table")
    mode.add_argument("--charts", action="store_true", help="regenerate charts")
    mode.add_argument("--discover", action="store_true", help="refresh the mod list from profile")
    mode.add_argument("--install-scheduler", action="store_true", help="create the Task Scheduler job")
    mode.add_argument("--remove-scheduler", action="store_true", help="delete the Task Scheduler job")
    mode.add_argument("--notify-off", action="store_true", help="run poll without notifications")
    args = parser.parse_args()

    config = load_config(args.config)
    setup_logging(config)
    transport.patch_moddb()

    storage = Storage(config["paths"]["db"])
    try:
        if args.init:
            return run_init(storage, config)
        if args.poll:
            return run_poll(storage, config, notify=not args.notify_off)
        if args.report:
            return run_report(storage, config)
        if args.charts:
            import charts
            charts.generate_all(storage, Path(config["paths"]["output"]))
            print("Charts regenerated in", config["paths"]["output"])
            return 0
        if args.discover:
            found = discover_mods(storage, config)
            print(f"Tracked {len(found)} mod(s).")
            return 0
        if args.install_scheduler:
            return install_scheduler(config)
        if args.remove_scheduler:
            return remove_scheduler()
        parser.print_help()
        return 0
    finally:
        storage.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Fatal error: %s", exc)
        sys.exit(1)
