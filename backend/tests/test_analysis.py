"""Synthetic Elexon-shaped fixture records; no test downloads live data."""

import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.analysis import DataIntegrityError, analyze, delivery_intervals


FIXTURES = Path(__file__).parent / "fixtures"
METADATA = {"refreshed_at": "2026-02-02T00:00:00Z", "windows": [], "forecast_rows": 6, "actual_rows": 2}


def rows(name):
    return json.loads((FIXTURES / name).read_text())


def test_latest_eligible_forecast_including_exact_cutoff_and_prior_day():
    result = analyze(METADATA, rows("forecast.json"), rows("actual.json"), "12:00")
    jan2 = result["intervals"][0]
    assert jan2["decision_date"] == "2026-01-01"
    assert jan2["forecast_mw"] == 110
    assert jan2["forecast_publish_time_utc"] == "2026-01-01T12:00:00Z"
    assert jan2["signed_error_mw"] == -10
    assert result["intervals"][1]["forecast_mw"] is None
    assert result["intervals"][-1]["decision_date"] == "2026-01-31"
    feb1 = next(row for row in result["intervals"] if row["start_time_utc"] == "2026-02-01T00:00:00Z")
    assert feb1["forecast_mw"] == 90
    assert feb1["forecast_publish_time_utc"] == "2026-01-31T11:30:00Z"
    assert len(result["intervals"]) == 31 * 48


def test_earlier_cutoff_selects_earlier_revision():
    result = analyze(METADATA, rows("forecast.json"), rows("actual.json"), "10:00")
    assert result["intervals"][0]["forecast_mw"] == 100
    assert result["intervals"][0]["forecast_publish_time_utc"] == "2026-01-01T09:30:00Z"


def test_duplicates_missing_and_latest_actual_revision():
    forecasts = rows("forecast.json")
    actuals = rows("actual.json")
    forecasts.append(forecasts[2].copy())
    actuals.append(actuals[0].copy())
    actuals.append({**actuals[0], "publishTime": "2026-01-02T02:00:00Z", "generation": 115})
    result = analyze(METADATA, forecasts, actuals, "12:00")
    assert result["intervals"][0]["actual_mw"] == 115
    assert result["accuracy"]["matched_intervals"] == 2
    assert result["accuracy"]["missing_actual_intervals"] == 31 * 48 - 2
    assert result["accuracy"]["missing_forecast_intervals"] == 31 * 48 - 2


def test_null_latest_revision_does_not_fall_back():
    forecasts = rows("forecast.json")
    forecasts[2]["generation"] = None
    result = analyze(METADATA, forecasts, rows("actual.json"), "12:00")
    assert result["intervals"][0]["forecast_mw"] is None
    assert result["intervals"][0]["forecast_publish_time_utc"] == "2026-01-01T12:00:00Z"
    assert result["accuracy"]["matched_intervals"] == 1


def test_exact_utc_timestamp_matching_and_metrics():
    forecasts = [
        {"dataset": "WINDFOR", "publishTime": "2026-01-01T09:30:00Z", "startTime": "2026-01-02T00:00:00Z", "generation": 13},
        {"dataset": "WINDFOR", "publishTime": "2026-01-01T09:30:00Z", "startTime": "2026-01-02T01:00:00Z", "generation": 16},
    ]
    actuals = [
        {"dataset": "FUELHH", "fuelType": "WIND", "publishTime": None, "startTime": "2026-01-02T00:00:00+00:00", "generation": 10},
        {"dataset": "FUELHH", "fuelType": "WIND", "publishTime": None, "startTime": "2026-01-02T01:00:00Z", "generation": 20},
        {"dataset": "FUELHH", "fuelType": "WIND", "publishTime": None, "startTime": "2026-01-02T00:30:00Z", "generation": 999},
    ]
    result = analyze(METADATA, forecasts, actuals, "12:00")
    assert result["intervals"][0]["signed_error_mw"] == 3
    assert result["intervals"][1]["signed_error_mw"] is None
    assert result["accuracy"]["mae_mw"] == 3.5
    assert result["accuracy"]["rmse_mw"] == pytest.approx(math.sqrt(12.5))
    assert result["accuracy"]["bias_mw"] == -0.5
    assert result["accuracy"]["matched_intervals"] == 2


def test_conflicting_duplicate_is_explicit_error():
    forecasts = rows("forecast.json")
    forecasts.append({**forecasts[2], "generation": 111})
    with pytest.raises(DataIntegrityError, match="Conflicting WINDFOR duplicate"):
        analyze(METADATA, forecasts, rows("actual.json"), "12:00")


def test_dst_delivery_intervals_are_utc_safe():
    # Generic generator also works for the 2026 UK clock changes, outside the scoped analysis.
    assert len(list(delivery_intervals(date(2026, 3, 28)))) == 46
    assert len(list(delivery_intervals(date(2026, 10, 24)))) == 50
    assert list(delivery_intervals(date(2026, 3, 28)))[0].tzinfo == timezone.utc
