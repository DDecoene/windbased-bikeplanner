"""Lichtgewicht analytics op basis van SQLite.

Slaat paginabezoeken en route-events op in analytics_data/analytics.db.
Geen cookies, geen externe diensten.
"""

import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "analytics_data")
DB_PATH = os.path.join(DB_DIR, "analytics.db")

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Eén connectie per thread (SQLite is niet thread-safe op dezelfde conn)."""
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(DB_DIR, exist_ok=True)
        _local.conn = sqlite3.connect(DB_PATH)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
    return _local.conn


@contextmanager
def _cursor():
    conn = _get_conn()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db() -> None:
    """Maak tabellen aan als ze niet bestaan."""
    with _cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS page_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                path TEXT,
                referrer TEXT,
                utm_source TEXT,
                utm_medium TEXT,
                utm_campaign TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS route_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id TEXT,
                distance_requested REAL,
                distance_actual REAL,
                duration_total REAL,
                duration_per_km REAL,
                duration_geocoding REAL,
                duration_graph REAL,
                duration_loop REAL,
                duration_finalize REAL,
                junction_count INTEGER,
                wind_speed REAL,
                planned_ride INTEGER DEFAULT 0,
                success INTEGER DEFAULT 1,
                error_type TEXT
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_pv_timestamp ON page_views(timestamp)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_re_timestamp ON route_events(timestamp)
        """)


def log_pageview(
    path: str,
    referrer: str | None = None,
    utm_source: str | None = None,
    utm_medium: str | None = None,
    utm_campaign: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _cursor() as cur:
        cur.execute(
            """INSERT INTO page_views (timestamp, path, referrer, utm_source, utm_medium, utm_campaign)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (now, path, referrer, utm_source, utm_medium, utm_campaign),
        )


def log_route_event(
    user_id: str,
    distance_requested: float,
    distance_actual: float | None,
    timings: dict | None,
    junction_count: int | None,
    wind_speed: float | None,
    planned_ride: bool,
    success: bool,
    error_type: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    duration_total = timings.get("total_duration") if timings else None
    duration_per_km = None
    if duration_total and distance_actual and distance_actual > 0:
        duration_per_km = round(duration_total / distance_actual, 4)

    with _cursor() as cur:
        cur.execute(
            """INSERT INTO route_events
               (timestamp, user_id, distance_requested, distance_actual,
                duration_total, duration_per_km,
                duration_geocoding, duration_graph, duration_loop, duration_finalize,
                junction_count, wind_speed, planned_ride, success, error_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                now,
                user_id,
                distance_requested,
                distance_actual,
                duration_total,
                duration_per_km,
                timings.get("geocoding_and_weather") if timings else None,
                timings.get("graph_download_and_prep") if timings else None,
                timings.get("loop_finding_algorithm") if timings else None,
                timings.get("route_finalizing") if timings else None,
                junction_count,
                wind_speed,
                1 if planned_ride else 0,
                1 if success else 0,
                error_type,
            ),
        )


def get_summary(start_date: str, end_date: str) -> dict:
    """Haal samenvatting op voor het dashboard.

    start_date en end_date zijn ISO-datums (YYYY-MM-DD).
    end_date is inclusief (tot middernacht van de dag erna).
    """
    end_exclusive = end_date + "T23:59:59"
    with _cursor() as cur:
        # Paginabezoeken totaal
        cur.execute(
            "SELECT COUNT(*) FROM page_views WHERE timestamp >= ? AND timestamp <= ?",
            (start_date, end_exclusive),
        )
        pageviews_total = cur.fetchone()[0]

        # Paginabezoeken per dag
        cur.execute(
            """SELECT DATE(timestamp) as dag, COUNT(*) as aantal
               FROM page_views
               WHERE timestamp >= ? AND timestamp <= ?
               GROUP BY dag ORDER BY dag""",
            (start_date, end_exclusive),
        )
        pageviews_by_day = [{"date": r["dag"], "count": r["aantal"]} for r in cur.fetchall()]

        # Paginabezoeken per pagina
        cur.execute(
            """SELECT path, COUNT(*) as aantal
               FROM page_views
               WHERE timestamp >= ? AND timestamp <= ?
               GROUP BY path ORDER BY aantal DESC LIMIT 20""",
            (start_date, end_exclusive),
        )
        pageviews_by_page = [{"path": r["path"], "count": r["aantal"]} for r in cur.fetchall()]

        # Top referrers
        cur.execute(
            """SELECT referrer, COUNT(*) as aantal
               FROM page_views
               WHERE timestamp >= ? AND timestamp <= ?
                 AND referrer IS NOT NULL AND referrer != ''
               GROUP BY referrer ORDER BY aantal DESC LIMIT 20""",
            (start_date, end_exclusive),
        )
        top_referrers = [{"referrer": r["referrer"], "count": r["aantal"]} for r in cur.fetchall()]

        # UTM bronnen
        cur.execute(
            """SELECT utm_source, utm_medium, utm_campaign, COUNT(*) as aantal
               FROM page_views
               WHERE timestamp >= ? AND timestamp <= ?
                 AND utm_source IS NOT NULL
               GROUP BY utm_source, utm_medium, utm_campaign
               ORDER BY aantal DESC LIMIT 20""",
            (start_date, end_exclusive),
        )
        utm_sources = [
            {
                "source": r["utm_source"],
                "medium": r["utm_medium"],
                "campaign": r["utm_campaign"],
                "count": r["aantal"],
            }
            for r in cur.fetchall()
        ]

        # Routes totaal + geslaagd
        cur.execute(
            """SELECT COUNT(*) as totaal,
                      SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as geslaagd
               FROM route_events
               WHERE timestamp >= ? AND timestamp <= ?""",
            (start_date, end_exclusive),
        )
        row = cur.fetchone()
        routes_total = row["totaal"]
        routes_succeeded = row["geslaagd"] or 0

        # Routes per dag
        cur.execute(
            """SELECT DATE(timestamp) as dag, COUNT(*) as totaal,
                      SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as geslaagd
               FROM route_events
               WHERE timestamp >= ? AND timestamp <= ?
               GROUP BY dag ORDER BY dag""",
            (start_date, end_exclusive),
        )
        routes_by_day = [
            {"date": r["dag"], "total": r["totaal"], "succeeded": r["geslaagd"] or 0}
            for r in cur.fetchall()
        ]

        # Prestaties (alleen geslaagde routes)
        cur.execute(
            """SELECT AVG(duration_total) as gem_duur,
                      AVG(duration_per_km) as gem_duur_per_km,
                      AVG(duration_geocoding) as gem_geocoding,
                      AVG(duration_graph) as gem_graph,
                      AVG(duration_loop) as gem_loop,
                      AVG(duration_finalize) as gem_finalize
               FROM route_events
               WHERE timestamp >= ? AND timestamp <= ? AND success = 1""",
            (start_date, end_exclusive),
        )
        perf = cur.fetchone()
        performance = {
            "avg_duration_total": round(perf["gem_duur"], 2) if perf["gem_duur"] else None,
            "avg_duration_per_km": round(perf["gem_duur_per_km"], 4) if perf["gem_duur_per_km"] else None,
            "avg_geocoding": round(perf["gem_geocoding"], 2) if perf["gem_geocoding"] else None,
            "avg_graph": round(perf["gem_graph"], 2) if perf["gem_graph"] else None,
            "avg_loop": round(perf["gem_loop"], 2) if perf["gem_loop"] else None,
            "avg_finalize": round(perf["gem_finalize"], 2) if perf["gem_finalize"] else None,
        }

        # Prestaties per dag
        cur.execute(
            """SELECT DATE(timestamp) as dag,
                      AVG(duration_total) as gem_duur,
                      AVG(duration_per_km) as gem_duur_per_km
               FROM route_events
               WHERE timestamp >= ? AND timestamp <= ? AND success = 1
               GROUP BY dag ORDER BY dag""",
            (start_date, end_exclusive),
        )
        performance_by_day = [
            {
                "date": r["dag"],
                "avg_duration": round(r["gem_duur"], 2) if r["gem_duur"] else None,
                "avg_duration_per_km": round(r["gem_duur_per_km"], 4) if r["gem_duur_per_km"] else None,
            }
            for r in cur.fetchall()
        ]

        # Actieve gebruikers
        cur.execute(
            """SELECT COUNT(DISTINCT user_id) as actief
               FROM route_events
               WHERE timestamp >= ? AND timestamp <= ?""",
            (start_date, end_exclusive),
        )
        active_users = cur.fetchone()["actief"]

    return {
        "period": {"start": start_date, "end": end_date},
        "pageviews_total": pageviews_total,
        "pageviews_by_day": pageviews_by_day,
        "pageviews_by_page": pageviews_by_page,
        "top_referrers": top_referrers,
        "utm_sources": utm_sources,
        "routes_total": routes_total,
        "routes_succeeded": routes_succeeded,
        "routes_by_day": routes_by_day,
        "performance": performance,
        "performance_by_day": performance_by_day,
        "active_users": active_users,
    }
