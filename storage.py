"""SQLite persistence for the ModDB tracker.

Tables
------
mods        the tracked mods (discovered from the member profile or manual list)
snapshots   one row per poll per mod with current counters
comments    every comment seen on a tracked mod (comment id is the primary key)
events      notification-worthy events (downloads, comments, replies)
meta        small key/value store (last poll, member name, ...)
"""

from __future__ import annotations

import datetime
import json
import sqlite3
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCHEMA = """
CREATE TABLE IF NOT EXISTS mods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_id TEXT UNIQUE NOT NULL,
    url TEXT NOT NULL,
    name TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'mod',
    active INTEGER NOT NULL DEFAULT 1,
    favorite INTEGER NOT NULL DEFAULT 0,
    discovered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mod_id INTEGER NOT NULL REFERENCES mods(id),
    fetched_at TEXT NOT NULL,
    downloads_total INTEGER NOT NULL DEFAULT 0,
    downloads_today INTEGER NOT NULL DEFAULT 0,
    visits INTEGER NOT NULL DEFAULT 0,
    visits_today INTEGER NOT NULL DEFAULT 0,
    rank INTEGER,
    rank_total INTEGER,
    watchers INTEGER,
    rating REAL,
    files INTEGER
);
CREATE INDEX IF NOT EXISTS idx_snapshots_mod ON snapshots(mod_id, fetched_at);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY,
    mod_id INTEGER NOT NULL REFERENCES mods(id),
    author TEXT NOT NULL,
    author_url TEXT,
    content TEXT,
    posted_at TEXT,
    position INTEGER NOT NULL DEFAULT 0,
    parent_id INTEGER,
    seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_comments_mod ON comments(mod_id, posted_at);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    mod_id INTEGER,
    mod_name TEXT,
    message TEXT NOT NULL,
    url TEXT,
    notified INTEGER NOT NULL DEFAULT 0,
    seen INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_events_notified ON events(notified);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def today_local() -> str:
    return datetime.date.today().isoformat()


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(mods)").fetchall()}
        if "content_type" not in cols:
            self.conn.execute(
                "ALTER TABLE mods ADD COLUMN content_type TEXT NOT NULL DEFAULT 'mod'"
            )
        if "favorite" not in cols:
            self.conn.execute(
                "ALTER TABLE mods ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0"
            )
        event_cols = {r[1] for r in self.conn.execute("PRAGMA table_info(events)").fetchall()}
        if "seen" not in event_cols:
            self.conn.execute(
                "ALTER TABLE events ADD COLUMN seen INTEGER NOT NULL DEFAULT 0"
            )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_events_seen ON events(seen)")

    def close(self) -> None:
        self.conn.close()

    # ---- meta ---------------------------------------------------------
    def meta_set(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self.conn.commit()

    def meta_get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    # ---- mods ---------------------------------------------------------
    def upsert_mod(self, name_id: str, url: str, name: str, content_type: str = "mod") -> int:
        cur = self.conn.execute(
            "INSERT INTO mods(name_id, url, name, content_type, discovered_at) VALUES(?, ?, ?, ?, ?) "
            "ON CONFLICT(name_id) DO UPDATE SET url = excluded.url, name = excluded.name, "
            "content_type = excluded.content_type, active = 1",
            (name_id, url, name, content_type, now_iso()),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT id FROM mods WHERE name_id = ?", (name_id,)).fetchone()
        return row["id"]

    def set_mod_active(self, name_id: str, active: bool) -> None:
        self.conn.execute("UPDATE mods SET active = ? WHERE name_id = ?", (1 if active else 0, name_id))
        self.conn.commit()

    def set_mod_favorite(self, name_id: str, favorite: bool) -> None:
        self.conn.execute("UPDATE mods SET favorite = ? WHERE name_id = ?", (1 if favorite else 0, name_id))
        self.conn.commit()

    def get_mods(self, active_only: bool = True) -> List[sqlite3.Row]:
        sql = "SELECT * FROM mods"
        if active_only:
            sql += " WHERE active = 1"
        return self.conn.execute(sql + " ORDER BY name COLLATE NOCASE").fetchall()

    def get_mod(self, name_id: str) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM mods WHERE name_id = ?", (name_id,)).fetchone()

    # ---- snapshots ----------------------------------------------------
    def add_snapshot(self, mod_id: int, **fields: Any) -> None:
        allowed = {
            "downloads_total",
            "downloads_today",
            "visits",
            "visits_today",
            "rank",
            "rank_total",
            "watchers",
            "rating",
            "files",
        }
        data = {k: v for k, v in fields.items() if k in allowed}
        data["fetched_at"] = now_iso()
        data["mod_id"] = mod_id
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        self.conn.execute(
            f"INSERT INTO snapshots({cols}) VALUES({placeholders})",
            tuple(data.values()),
        )
        self.conn.commit()

    def last_snapshot(self, mod_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM snapshots WHERE mod_id = ? ORDER BY fetched_at DESC LIMIT 1",
            (mod_id,),
        ).fetchone()

    def snapshots_for(self, mod_id: int) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM snapshots WHERE mod_id = ? ORDER BY fetched_at ASC", (mod_id,)
        ).fetchall()

    def snapshots_for_all(self, mod_ids: Optional[Iterable[int]] = None) -> Dict[int, List[sqlite3.Row]]:
        sql = "SELECT * FROM snapshots ORDER BY fetched_at ASC"
        if mod_ids is not None:
            ids = list(mod_ids)
            if not ids:
                return {}
            sql = f"SELECT * FROM snapshots WHERE mod_id IN ({','.join('?' for _ in ids)}) ORDER BY fetched_at ASC"
        rows = self.conn.execute(sql, tuple(ids) if mod_ids is not None else ()).fetchall()
        out: Dict[int, List[sqlite3.Row]] = {}
        for row in rows:
            out.setdefault(row["mod_id"], []).append(row)
        return out

    # ---- comments -----------------------------------------------------
    def comment_exists(self, comment_id: int) -> bool:
        return (
            self.conn.execute("SELECT 1 FROM comments WHERE id = ?", (comment_id,)).fetchone()
            is not None
        )

    def add_comment(
        self,
        comment_id: int,
        mod_id: int,
        author: str,
        content: Optional[str],
        posted_at: Optional[str],
        position: int,
        parent_id: Optional[int],
        author_url: Optional[str] = None,
    ) -> bool:
        """Returns True if the comment was newly inserted."""
        if self.comment_exists(comment_id):
            return False
        self.conn.execute(
            "INSERT INTO comments(id, mod_id, author, author_url, content, posted_at, position, parent_id, seen_at) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                comment_id,
                mod_id,
                author,
                author_url,
                content,
                posted_at,
                position,
                parent_id,
                now_iso(),
            ),
        )
        self.conn.commit()
        return True

    def get_comments_since(self, since_iso: Optional[str] = None, limit: int = 200) -> List[sqlite3.Row]:
        sql = "SELECT * FROM comments"
        args: Tuple = ()
        if since_iso:
            sql += " WHERE posted_at >= ?"
            args = (since_iso,)
        sql += " ORDER BY posted_at DESC LIMIT ?"
        return self.conn.execute(sql, args + (limit,)).fetchall()

    def recent_comments(self, limit: int = 50) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM comments ORDER BY posted_at DESC LIMIT ?", (limit,)
        ).fetchall()

    # ---- events -------------------------------------------------------
    def add_event(self, kind: str, message: str, mod_id: Optional[int] = None, mod_name: Optional[str] = None, url: Optional[str] = None) -> None:
        self.conn.execute(
            "INSERT INTO events(created_at, kind, mod_id, mod_name, message, url) VALUES(?, ?, ?, ?, ?, ?)",
            (now_iso(), kind, mod_id, mod_name, message, url),
        )
        self.conn.commit()

    def get_unnotified_events(self) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM events WHERE notified = 0 ORDER BY id ASC", ()
        ).fetchall()

    def mark_events_notified(self, ids: Iterable[int]) -> None:
        ids = list(ids)
        if not ids:
            return
        self.conn.executemany(
            "UPDATE events SET notified = 1 WHERE id = ?", [(i,) for i in ids]
        )
        self.conn.commit()

    def recent_events(self, limit: int = 50) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    def count_unseen(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS n FROM events WHERE seen = 0").fetchone()
        return int(row["n"] or 0)

    def unseen_events(self, limit: int = 200) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM events WHERE seen = 0 ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    def mark_events_seen(self, ids: Optional[Iterable[int]] = None) -> int:
        if ids is None:
            self.conn.execute("UPDATE events SET seen = 1 WHERE seen = 0")
        else:
            ids = [int(i) for i in ids if i]
            if not ids:
                return 0
            placeholders = ",".join("?" for _ in ids)
            self.conn.execute(
                f"UPDATE events SET seen = 1 WHERE id IN ({placeholders})", tuple(ids)
            )
        self.conn.commit()
        return self.conn.total_changes

    # ---- stats helpers for charts ------------------------------------
    def totals_per_mod(self) -> List[Dict[str, Any]]:
        """Latest snapshot per mod, as dicts (incl. comment/reply counts)."""
        rows = self.conn.execute(
            """
            SELECT m.id, m.name, m.name_id, m.url, s.downloads_total, s.downloads_today,
                   s.visits, s.visits_today, s.rank, s.rank_total, s.watchers, s.rating, s.files,
                   (SELECT COUNT(*) FROM comments c WHERE c.mod_id = m.id) AS comments,
                   (SELECT COUNT(*) FROM comments c WHERE c.mod_id = m.id AND c.parent_id IS NOT NULL) AS replies,
                   m.favorite
            FROM mods m
            JOIN snapshots s ON s.id = (
                SELECT s2.id FROM snapshots s2
                WHERE s2.mod_id = m.id ORDER BY s2.fetched_at DESC LIMIT 1
            )
            WHERE m.active = 1
            ORDER BY s.downloads_total DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]

    def dashboard_stats(self, days: int = 30) -> Dict[str, Any]:
        """Aggregate numbers for the dashboard stat cards."""
        totals = self.totals_per_mod()
        total_downloads = sum(int(t["downloads_total"] or 0) for t in totals)
        today_downloads = sum(int(t["downloads_today"] or 0) for t in totals)
        comments = sum(int(t["comments"] or 0) for t in totals)
        replies = sum(int(t["replies"] or 0) for t in totals)

        day_deltas = self.daily_download_deltas(days=days)
        week = sum(v for d, v in day_deltas if (datetime.date.today() - d).days < 7)
        month = sum(v for d, v in day_deltas if (datetime.date.today() - d).days < days)

        avg_per_day = round(month / days, 1) if days else 0.0

        fastest = None
        per_mod_week: Dict[str, int] = {}
        for mod_id, snaps in self.snapshots_for_all([t["id"] for t in totals]).items():
            name = next((t["name"] for t in totals if t["id"] == mod_id), str(mod_id))
            per_mod_week[name] = 0
            prev = None
            for s in snaps:
                d = datetime.date.fromisoformat(s["fetched_at"][:10])
                if (datetime.date.today() - d).days < 7:
                    total = int(s["downloads_total"] or 0)
                    if prev is not None and total > prev:
                        per_mod_week[name] += total - prev
                    prev = max(prev or 0, total)
                else:
                    prev = max(prev or 0, int(s["downloads_total"] or 0))
        if per_mod_week:
            fastest = max(per_mod_week, key=per_mod_week.get)
            if per_mod_week[fastest] <= 0:
                fastest = None

        return {
            "total_downloads": total_downloads,
            "today_downloads": today_downloads,
            "week_downloads": week,
            "month_downloads": month,
            "avg_per_day": avg_per_day,
            "comments": comments,
            "replies": replies,
            "tracked_mods": len(totals),
            "fastest_mod": fastest,
            "fastest_delta": per_mod_week.get(fastest, 0) if fastest else 0,
        }

    def daily_download_deltas(self, days: int = 30) -> List[tuple]:
        """Downloads gained per day (summed across all mods) for the last `days` days."""
        rows = self.conn.execute(
            """
            SELECT mod_id, date(fetched_at) AS day, MAX(downloads_total) AS total
            FROM snapshots
            WHERE fetched_at >= date('now', ?)
            GROUP BY mod_id, day
            ORDER BY day
            """,
            (f"-{days} days",),
        ).fetchall()

        by_mod: Dict[int, Dict[str, int]] = {}
        for r in rows:
            by_mod.setdefault(r["mod_id"], {})[r["day"]] = int(r["total"] or 0)

        per_day: Dict[datetime.date, int] = {}
        for _, days_map in by_mod.items():
            prev = None
            for day in sorted(days_map):
                d = datetime.date.fromisoformat(day)
                total = days_map[day]
                if prev is not None and total > prev:
                    per_day[d] = per_day.get(d, 0) + (total - prev)
                prev = total if prev is None else max(prev, total)
        return sorted(per_day.items())

    def comment_counts_per_day(self, mod_ids: Optional[List[int]] = None, days: int = 60) -> List[sqlite3.Row]:
        if mod_ids:
            placeholders = ",".join("?" for _ in mod_ids)
            return self.conn.execute(
                f"""
                SELECT date(posted_at) AS day, COUNT(*) AS n
                FROM comments
                WHERE mod_id IN ({placeholders}) AND posted_at >= date('now', ?)
                GROUP BY day ORDER BY day
                """,
                (*mod_ids, f"-{days} days"),
            ).fetchall()
        return self.conn.execute(
            """
            SELECT date(posted_at) AS day, COUNT(*) AS n
            FROM comments
            WHERE posted_at >= date('now', ?)
            GROUP BY day ORDER BY day
            """,
            (f"-{days} days",),
        ).fetchall()

    @staticmethod
    def snapshot_json(snapshot: sqlite3.Row) -> Dict[str, Any]:
        return dict(snapshot)

    def export_json(self, path: str) -> None:
        data = {
            "mods": [dict(r) for r in self.conn.execute("SELECT * FROM mods").fetchall()],
            "snapshots": [dict(r) for r in self.conn.execute("SELECT * FROM snapshots").fetchall()],
            "comments": [dict(r) for r in self.conn.execute("SELECT * FROM comments").fetchall()],
            "events": [dict(r) for r in self.conn.execute("SELECT * FROM events").fetchall()],
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)
