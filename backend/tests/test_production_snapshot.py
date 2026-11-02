"""Production snapshot tests use the committed Elexon asset, never a live API call."""

import json
import math
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.analysis import analyze
from app.cache import CacheUnavailable
from app.snapshot_store import MANIFEST_PATH, load_snapshot


client = TestClient(main.app)


def test_bundled_snapshot_has_verified_source_rows():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    metadata, forecasts, actuals = load_snapshot()
    assert len(forecasts) == manifest["forecast_rows"] == metadata["forecast_rows"]
    assert len(actuals) == manifest["actual_rows"] == metadata["actual_rows"]
    assert all(row["dataset"] == "WINDFOR" for row in forecasts)
    assert all(row["dataset"] == "FUELHH" and row["fuelType"] == "WIND" for row in actuals)
    result = analyze(metadata, forecasts, actuals, "12:00")
    assert len(result["intervals"]) == 1488
    assert all(row["forecast_publish_time_utc"] <= row["decision_cutoff_utc"]
               for row in result["intervals"] if row["forecast_publish_time_utc"])


def test_missing_and_corrupt_snapshot_fail_closed(tmp_path, monkeypatch):
    with pytest.raises(CacheUnavailable, match="missing"):
        load_snapshot(tmp_path / "missing.json")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    copied_manifest = tmp_path / "manifest.json"
    copied_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    artifact = tmp_path / manifest["file"]
    shutil.copyfile(MANIFEST_PATH.parent / manifest["file"], artifact)
    artifact.write_bytes(artifact.read_bytes() + b"corrupt")
    with pytest.raises(CacheUnavailable, match="checksum"):
        load_snapshot(copied_manifest)
    monkeypatch.delenv("ELEXON_CACHE_PATH", raising=False)
    monkeypatch.setenv("SNAPSHOT_REQUIRED", "1")
    monkeypatch.setattr(main, "MANIFEST_PATH", copied_manifest)
    main._analyzed_snapshot.cache_clear()
    response = client.get("/api/summary")
    assert response.status_code == 503
    assert "checksum" in response.json()["detail"]
    manifest["file"] = "../outside.json.gz"
    copied_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CacheUnavailable, match="unsafe snapshot filename"):
        load_snapshot(copied_manifest)


def test_production_routes_use_bundle_without_sqlite(monkeypatch):
    monkeypatch.delenv("ELEXON_CACHE_PATH", raising=False)
    monkeypatch.setenv("SNAPSHOT_REQUIRED", "1")
    monkeypatch.setattr(main, "load", lambda _path: pytest.fail("SQLite must not be read for a bundled deployment"))
    main._analyzed_snapshot.cache_clear()
    health = client.get("/api/health")
    summary = client.get("/api/summary")
    series = client.get("/api/timeseries?decision_date=2026-01-31")
    accuracy = client.get("/api/accuracy")
    filtered = client.get("/api/accuracy?decision_date_from=2026-01-31&decision_date_to=2026-01-31")
    assert all(response.status_code == 200 for response in (health, summary, series, accuracy, filtered))
    assert summary.json()["accuracy"] == accuracy.json()
    assert summary.json()["source_rows"]["WINDFOR"] > 0
    assert len(series.json()["intervals"]) == 48
    assert filtered.json()["matched_intervals"] == sum(row["signed_error_mw"] is not None for row in series.json()["intervals"])
    assert filtered.json()["missing_forecast_intervals"] == sum(row["forecast_mw"] is None for row in series.json()["intervals"])
    errors = [row["signed_error_mw"] for row in series.json()["intervals"] if row["signed_error_mw"] is not None]
    assert math.isclose(filtered.json()["mae_mw"], sum(abs(error) for error in errors) / len(errors))
    assert math.isclose(filtered.json()["rmse_mw"], math.sqrt(sum(error * error for error in errors) / len(errors)))
    assert math.isclose(filtered.json()["bias_mw"], sum(errors) / len(errors))
    assert health.headers["x-content-type-options"] == "nosniff"
    assert "access-control-allow-origin" not in client.get("/api/health", headers={"Origin": "https://unrelated.example"}).headers


def test_required_bundle_missing_returns_503(monkeypatch, tmp_path):
    monkeypatch.delenv("ELEXON_CACHE_PATH", raising=False)
    monkeypatch.setenv("SNAPSHOT_REQUIRED", "1")
    monkeypatch.setattr(main, "MANIFEST_PATH", tmp_path / "missing.json")
    main._analyzed_snapshot.cache_clear()
    response = client.get("/api/summary")
    assert response.status_code == 503
    assert "Bundled historical snapshot" in response.json()["detail"]
