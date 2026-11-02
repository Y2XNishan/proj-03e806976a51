import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.analysis import DataIntegrityError
from app.cache import load, refresh
from app.main import _analyzed_snapshot, app


client = TestClient(app)
FIXTURES = Path(__file__).parent / "fixtures"


def seeded_cache(path: Path, forecasts=None):
    forecasts = forecasts if forecasts is not None else json.loads((FIXTURES / "forecast.json").read_text())
    actuals = json.loads((FIXTURES / "actual.json").read_text())
    metadata = {"refreshed_at": "2026-02-02T00:00:00Z", "windows": [],
                "forecast_rows": len(forecasts), "actual_rows": len(actuals)}
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE snapshot (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("CREATE TABLE source_rows (dataset TEXT, payload TEXT)")
        conn.execute("INSERT INTO snapshot VALUES (?, ?)", ("metadata", json.dumps(metadata)))
        conn.executemany("INSERT INTO source_rows VALUES (?, ?)",
                         [("WINDFOR", json.dumps(row)) for row in forecasts] + [("FUELHH", json.dumps(row)) for row in actuals])


def test_missing_cache_returns_descriptive_503(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEXON_CACHE_PATH", str(tmp_path / "absent.db"))
    _analyzed_snapshot.cache_clear()
    response = client.get("/api/summary")
    assert response.status_code == 503
    assert "refresh" in response.json()["detail"]


def test_source_backed_endpoints_and_date_filter(tmp_path, monkeypatch):
    path = tmp_path / "fixture.db"
    seeded_cache(path)
    monkeypatch.setenv("ELEXON_CACHE_PATH", str(path))
    _analyzed_snapshot.cache_clear()
    summary = client.get("/api/summary")
    assert summary.status_code == 200
    assert summary.json()["expected_intervals"] == 1488
    assert summary.json()["accuracy"]["matched_intervals"] == 2
    assert summary.json()["sources"]["forecast"].endswith("/WINDFOR/stream")
    series = client.get("/api/timeseries?decision_date=2026-01-31")
    assert series.status_code == 200
    assert len(series.json()["intervals"]) == 48
    assert series.json()["intervals"][0]["start_time_utc"] == "2026-02-01T00:00:00Z"
    assert client.get("/api/accuracy").json()["matched_intervals"] == 2
    one_day = client.get("/api/accuracy?decision_date_from=2026-01-31&decision_date_to=2026-01-31")
    assert one_day.status_code == 200
    assert one_day.json()["matched_intervals"] == 1
    assert one_day.json()["bias_mw"] == -10
    assert one_day.json()["missing_forecast_intervals"] == 47


def test_invalid_decision_date_and_bad_cache(tmp_path, monkeypatch):
    assert client.get("/api/timeseries?decision_date=2026-02-01").status_code == 400
    assert client.get("/api/timeseries?decision_date=nope").status_code == 422
    assert client.get("/api/accuracy?decision_date_from=2026-01-01").status_code == 400
    assert client.get("/api/accuracy?decision_date_from=2026-01-31&decision_date_to=2026-01-01").status_code == 400
    path = tmp_path / "bad.db"
    forecasts = json.loads((FIXTURES / "forecast.json").read_text())
    forecasts[0]["publishTime"] = None
    seeded_cache(path, forecasts)
    monkeypatch.setenv("ELEXON_CACHE_PATH", str(path))
    _analyzed_snapshot.cache_clear()
    response = client.get("/api/accuracy")
    assert response.status_code == 503
    assert "publishTime" in response.json()["detail"]


def test_failed_refresh_keeps_previous_complete_snapshot(tmp_path):
    path = tmp_path / "existing.db"
    seeded_cache(path)

    class BrokenSource:
        def forecast_publish_day(self, _day):
            return [{"dataset": "WINDFOR", "publishTime": None,
                     "startTime": "2026-01-02T00:00:00Z", "generation": 1}]

        def actual_day(self, _day):
            return [{"dataset": "FUELHH", "fuelType": "WIND", "publishTime": None,
                     "startTime": "2026-01-02T00:00:00Z", "generation": 1}]

    with pytest.raises(DataIntegrityError, match="publishTime"):
        refresh(path, BrokenSource())
    metadata, forecasts, actuals = load(path)
    assert metadata["forecast_rows"] == 6
    assert len(forecasts) == 6 and len(actuals) == 2
