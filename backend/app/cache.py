"""Small local snapshot: refresh atomically, then serve without upstream calls."""

import json
import os
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .analysis import analyze
from .elexon import ElexonClient, ElexonError, each_day


DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "elexon.sqlite3"


class CacheUnavailable(Exception):
    pass


def cache_path() -> Path:
    return Path(os.getenv("ELEXON_CACHE_PATH", str(DEFAULT_DB)))


def refresh(path: Path | None = None, client: ElexonClient | None = None) -> dict[str, Any]:
    path = path or cache_path()
    upstream = client or ElexonClient()
    rows: list[tuple[str, str]] = []
    forecast_records: list[dict[str, Any]] = []
    actual_records: list[dict[str, Any]] = []
    windows: list[dict[str, Any]] = []
    try:
        # Publication windows start one day before the first January decision.
        for day in each_day(date(2025, 12, 31), date(2026, 1, 31)):
            batch = upstream.forecast_publish_day(day)
            forecast_records.extend(batch)
            rows.extend(("WINDFOR", json.dumps(row, separators=(",", ":"))) for row in batch)
            windows.append({"dataset": "WINDFOR", "date": day.isoformat(), "rows": len(batch)})
        # Next-day delivery from January 31 belongs to February 1.
        for day in each_day(date(2026, 1, 2), date(2026, 2, 1)):
            batch = upstream.actual_day(day)
            actual_records.extend(batch)
            rows.extend(("FUELHH", json.dumps(row, separators=(",", ":"))) for row in batch)
            windows.append({"dataset": "FUELHH", "date": day.isoformat(), "rows": len(batch)})
    finally:
        if client is None:
            upstream.close()

    if not any(dataset == "WINDFOR" for dataset, _ in rows) or not any(dataset == "FUELHH" for dataset, _ in rows):
        raise ElexonError("Refresh returned no records for one or both required datasets; previous cache retained")
    metadata = {"refreshed_at": datetime.now(timezone.utc).isoformat(), "windows": windows,
                "forecast_rows": sum(dataset == "WINDFOR" for dataset, _ in rows),
                "actual_rows": sum(dataset == "FUELHH" for dataset, _ in rows)}
    # Validate the full source snapshot before replacing a previously usable cache.
    analyze(metadata, forecast_records, actual_records, os.getenv("DAY_AHEAD_CUTOFF_LOCAL", "12:00"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS source_rows (dataset TEXT NOT NULL, payload TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS snapshot (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        with conn:
            conn.execute("DELETE FROM source_rows")
            conn.execute("DELETE FROM snapshot")
            conn.executemany("INSERT INTO source_rows VALUES (?, ?)", rows)
            conn.execute("INSERT INTO snapshot VALUES (?, ?)", ("metadata", json.dumps(metadata)))
    return metadata


def load(path: Path | None = None) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    path = path or cache_path()
    if not path.exists():
        raise CacheUnavailable("Elexon cache is absent; run `python -m app.refresh` from backend first")
    try:
        with sqlite3.connect(path) as conn:
            item = conn.execute("SELECT value FROM snapshot WHERE key = 'metadata'").fetchone()
            if item is None:
                raise CacheUnavailable("Elexon cache has no complete snapshot; run refresh")
            records = conn.execute("SELECT dataset, payload FROM source_rows").fetchall()
        forecasts = [json.loads(payload) for dataset, payload in records if dataset == "WINDFOR"]
        actuals = [json.loads(payload) for dataset, payload in records if dataset == "FUELHH"]
        return json.loads(item[0]), forecasts, actuals
    except sqlite3.Error as exc:
        raise CacheUnavailable(f"Elexon cache cannot be read: {exc}") from exc
