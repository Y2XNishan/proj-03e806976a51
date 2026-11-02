"""Point-in-time day-ahead selection and exact-interval accuracy."""

import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

from .elexon import FUELHH_URL, WINDFOR_URL, each_day


LONDON = ZoneInfo("Europe/London")
FIRST_DECISION = date(2026, 1, 1)
LAST_DECISION = date(2026, 1, 31)


class DataIntegrityError(Exception):
    pass


def timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise DataIntegrityError(f"Missing or invalid {field} timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DataIntegrityError(f"Invalid {field} timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise DataIntegrityError(f"{field} timestamp has no timezone: {value}")
    return parsed.astimezone(timezone.utc)


def generation(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise DataIntegrityError(f"Invalid generation value: {value!r}")
    return float(value)


def iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value is not None else None


def cutoff_time(value: str) -> time:
    try:
        parsed = time.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("DAY_AHEAD_CUTOFF_LOCAL must be HH:MM in Europe/London") from exc
    if parsed.tzinfo is not None or parsed.second or parsed.microsecond:
        raise ValueError("DAY_AHEAD_CUTOFF_LOCAL must be HH:MM in Europe/London")
    return parsed


def delivery_intervals(decision_day: date):
    local_start = datetime.combine(decision_day + timedelta(days=1), time.min, LONDON)
    local_end = datetime.combine(decision_day + timedelta(days=2), time.min, LONDON)
    current = local_start.astimezone(timezone.utc)
    end = local_end.astimezone(timezone.utc)
    while current < end:
        yield current
        current += timedelta(minutes=30)


def _index_forecasts(rows: list[dict[str, Any]]) -> dict[datetime, list[tuple[datetime, float | None]]]:
    unique: dict[tuple[datetime, datetime], float | None] = {}
    for row in rows:
        if row.get("dataset") != "WINDFOR":
            raise DataIntegrityError("WINDFOR cache contains an unexpected dataset")
        start = timestamp(row.get("startTime"), "WINDFOR startTime")
        published = timestamp(row.get("publishTime"), "WINDFOR publishTime")
        value = generation(row.get("generation"))
        key = (start, published)
        if key in unique and unique[key] != value:
            raise DataIntegrityError(f"Conflicting WINDFOR duplicate for {iso(start)} at {iso(published)}")
        unique[key] = value
    grouped: dict[datetime, list[tuple[datetime, float | None]]] = defaultdict(list)
    for (start, published), value in unique.items():
        grouped[start].append((published, value))
    for revisions in grouped.values():
        revisions.sort(key=lambda pair: pair[0])
    return grouped


def _index_actuals(rows: list[dict[str, Any]]) -> dict[datetime, tuple[datetime | None, float | None]]:
    unique: dict[tuple[datetime, datetime | None], float | None] = {}
    for row in rows:
        if row.get("dataset") != "FUELHH" or row.get("fuelType") != "WIND":
            raise DataIntegrityError("FUELHH cache contains an unexpected dataset or fuel type")
        start = timestamp(row.get("startTime"), "FUELHH startTime")
        published = timestamp(row["publishTime"], "FUELHH publishTime") if row.get("publishTime") else None
        value = generation(row.get("generation"))
        key = (start, published)
        if key in unique and unique[key] != value:
            raise DataIntegrityError(f"Conflicting FUELHH duplicate for {iso(start)} at {iso(published)}")
        unique[key] = value
    latest: dict[datetime, tuple[datetime | None, float | None]] = {}
    for (start, published), value in unique.items():
        if start not in latest or (published or datetime.min.replace(tzinfo=timezone.utc)) > (latest[start][0] or datetime.min.replace(tzinfo=timezone.utc)):
            latest[start] = (published, value)
    return latest


def calculate_accuracy(intervals: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate one window directly from matched interval errors, never daily aggregates."""
    errors = [row["signed_error_mw"] for row in intervals if row["signed_error_mw"] is not None]
    return {
        "matched_intervals": len(errors),
        "missing_actual_intervals": sum(row["actual_mw"] is None for row in intervals),
        "missing_forecast_intervals": sum(row["forecast_mw"] is None for row in intervals),
        "mae_mw": mean(abs(error) for error in errors) if errors else None,
        "rmse_mw": math.sqrt(mean(error * error for error in errors)) if errors else None,
        "bias_mw": mean(errors) if errors else None,
    }


def analyze(metadata: dict[str, Any], forecast_rows: list[dict[str, Any]], actual_rows: list[dict[str, Any]], cutoff_local: str) -> dict[str, Any]:
    clock = cutoff_time(cutoff_local)
    forecasts = _index_forecasts(forecast_rows)
    actuals = _index_actuals(actual_rows)
    intervals: list[dict[str, Any]] = []
    missing_actual = missing_forecast = 0
    for day in each_day(FIRST_DECISION, LAST_DECISION):
        decision = datetime.combine(day, clock, LONDON).astimezone(timezone.utc)
        for start in delivery_intervals(day):
            eligible = [item for item in forecasts.get(start, ()) if item[0] <= decision]
            selected = eligible[-1] if eligible else None
            forecast = selected[1] if selected else None
            actual = actuals.get(start, (None, None))[1]
            if forecast is None:
                missing_forecast += 1
            if actual is None:
                missing_actual += 1
            error = forecast - actual if forecast is not None and actual is not None else None
            intervals.append({
                "decision_date": day.isoformat(), "decision_cutoff_utc": iso(decision),
                "start_time_utc": iso(start), "forecast_publish_time_utc": iso(selected[0]) if selected else None,
                "forecast_mw": forecast, "actual_mw": actual, "signed_error_mw": error,
            })
    empty_windows = [f"{window['dataset']} {window['date']}" for window in metadata.get("windows", []) if window["rows"] == 0]
    warnings = []
    if empty_windows:
        warnings.append("Source returned no records for: " + ", ".join(empty_windows))
    if missing_forecast:
        warnings.append("Some delivery intervals lack an eligible exact-start WINDFOR value; no interpolation was used.")
    if forecasts and all(start.minute == 0 for start in forecasts):
        warnings.append("WINDFOR targets in this snapshot have hourly starts; matched values compare an hourly target with a FUELHH half-hour average.")
    if missing_actual:
        warnings.append("Some delivery intervals lack a non-null FUELHH value.")
    accuracy = calculate_accuracy(intervals)
    return {"metadata": metadata, "intervals": intervals, "accuracy": accuracy, "warnings": warnings,
            "cutoff_local": cutoff_local, "sources": {"actual": FUELHH_URL, "forecast": WINDFOR_URL}}
