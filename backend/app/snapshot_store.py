"""Content-addressed, read-only export of the verified Elexon cache."""

import argparse
import gzip
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from .analysis import analyze
from .cache import CacheUnavailable, load
from .elexon import FUELHH_URL, WINDFOR_URL, each_day


SNAPSHOT_DIR = Path(__file__).resolve().parents[1] / "snapshots"
MANIFEST_PATH = SNAPSHOT_DIR / "manifest.json"
SCHEMA_VERSION = 1
FILE_PATTERN = re.compile(r"elexon-2026-01-[0-9a-f]{12}\.json\.gz\Z")


def _validate(metadata: dict[str, Any], forecasts: list[dict[str, Any]], actuals: list[dict[str, Any]]) -> None:
    expected = {
        *(('WINDFOR', day.isoformat()) for day in each_day(date(2025, 12, 31), date(2026, 1, 31))),
        *(('FUELHH', day.isoformat()) for day in each_day(date(2026, 1, 2), date(2026, 2, 1))),
    }
    windows = metadata.get("windows")
    if not isinstance(windows, list) or len(windows) != len(expected):
        raise CacheUnavailable("Snapshot does not contain all required source windows")
    found = {(row.get("dataset"), row.get("date")) for row in windows if isinstance(row, dict)}
    if found != expected or any(not isinstance(row.get("rows"), int) or row["rows"] <= 0 for row in windows):
        raise CacheUnavailable("Snapshot has missing, duplicate, or empty source windows")
    if metadata.get("forecast_rows") != len(forecasts) or metadata.get("actual_rows") != len(actuals):
        raise CacheUnavailable("Snapshot source row counts do not match metadata")
    if sum(row["rows"] for row in windows if row["dataset"] == "WINDFOR") != len(forecasts):
        raise CacheUnavailable("WINDFOR window counts do not match source rows")
    if sum(row["rows"] for row in windows if row["dataset"] == "FUELHH") != len(actuals):
        raise CacheUnavailable("FUELHH window counts do not match source rows")
    if not isinstance(metadata.get("refreshed_at"), str):
        raise CacheUnavailable("Snapshot is missing the source retrieval timestamp")
    # Validate every timestamp/value and the point-in-time selection before packaging.
    analyze(metadata, forecasts, actuals, "12:00")


def export_snapshot(cache_db: Path | None = None, manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    metadata, forecasts, actuals = load(cache_db)
    _validate(metadata, forecasts, actuals)
    forecasts = sorted(forecasts, key=lambda row: (str(row.get("publishTime")), str(row.get("startTime"))))
    actuals = sorted(actuals, key=lambda row: (str(row.get("startTime")), str(row.get("publishTime"))))
    payload = {"schema_version": SCHEMA_VERSION, "metadata": metadata,
               "forecasts": forecasts, "actuals": actuals}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    compressed = gzip.compress(encoded, compresslevel=9, mtime=0)
    digest = hashlib.sha256(compressed).hexdigest()
    filename = f"elexon-2026-01-{digest[:12]}.json.gz"
    manifest = {
        "schema_version": SCHEMA_VERSION, "file": filename, "sha256": digest,
        "compressed_bytes": len(compressed), "refreshed_at": metadata["refreshed_at"],
        "forecast_rows": len(forecasts), "actual_rows": len(actuals),
        "sources": {"forecast": WINDFOR_URL, "actual": FUELHH_URL},
        "decision_dates": ["2026-01-01", "2026-01-31"],
        "delivery_dates": ["2026-01-02", "2026-02-01"],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = manifest_path.parent / filename
    if artifact.exists() and artifact.read_bytes() != compressed:
        raise CacheUnavailable("Content-addressed snapshot filename collision")
    if not artifact.exists():
        artifact.write_bytes(compressed)
    temporary = manifest_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(manifest_path)
    return manifest


def load_snapshot(manifest_path: Path = MANIFEST_PATH) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    if not manifest_path.is_file():
        raise CacheUnavailable("Bundled historical snapshot is missing; export it from a verified Elexon cache")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        filename = manifest["file"]
        if manifest["schema_version"] != SCHEMA_VERSION or not isinstance(filename, str) or not FILE_PATTERN.fullmatch(filename):
            raise ValueError("unsupported manifest or unsafe snapshot filename")
        compressed = (manifest_path.parent / filename).read_bytes()
        if len(compressed) != manifest["compressed_bytes"] or hashlib.sha256(compressed).hexdigest() != manifest["sha256"]:
            raise ValueError("snapshot checksum mismatch")
        payload = json.loads(gzip.decompress(compressed).decode("utf-8"))
        if payload["schema_version"] != SCHEMA_VERSION:
            raise ValueError("unsupported snapshot schema")
        metadata, forecasts, actuals = payload["metadata"], payload["forecasts"], payload["actuals"]
        if not isinstance(metadata, dict) or not isinstance(forecasts, list) or not isinstance(actuals, list):
            raise ValueError("invalid snapshot structure")
        if manifest["forecast_rows"] != len(forecasts) or manifest["actual_rows"] != len(actuals):
            raise ValueError("manifest row counts do not match")
        if manifest["refreshed_at"] != metadata.get("refreshed_at") or manifest["sources"] != {"forecast": WINDFOR_URL, "actual": FUELHH_URL}:
            raise ValueError("manifest provenance does not match")
        _validate(metadata, forecasts, actuals)
        return metadata, forecasts, actuals
    except (OSError, ValueError, KeyError, TypeError, AttributeError, gzip.BadGzipFile) as exc:
        raise CacheUnavailable(f"Bundled historical snapshot failed integrity checks: {exc}") from exc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export a verified, read-only January 2026 Elexon snapshot")
    parser.add_argument("--cache", type=Path, help="SQLite cache from python -m app.refresh")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH, help="Output manifest path")
    arguments = parser.parse_args()
    print(json.dumps(export_snapshot(arguments.cache, arguments.manifest), indent=2))
