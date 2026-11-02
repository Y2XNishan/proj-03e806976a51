"""Public API contracts; MW values are generation power, not energy."""

from pydantic import BaseModel, Field


class Sources(BaseModel):
    actual: str
    forecast: str


class AccuracyResponse(BaseModel):
    matched_intervals: int = Field(description="Intervals with non-null forecast and actual values")
    missing_actual_intervals: int = Field(description="Expected intervals without a usable FUELHH value")
    missing_forecast_intervals: int = Field(description="Expected intervals without an eligible exact-start WINDFOR value")
    mae_mw: float | None = Field(description="Mean absolute forecast minus actual error, MW")
    rmse_mw: float | None = Field(description="Root mean squared forecast minus actual error, MW")
    bias_mw: float | None = Field(description="Mean signed forecast minus actual error, MW")


class IntervalResponse(BaseModel):
    decision_date: str = Field(description="Purchase decision date in Europe/London")
    decision_cutoff_utc: str
    start_time_utc: str = Field(description="Exact 30-minute delivery interval start")
    forecast_publish_time_utc: str | None = Field(description="Publication time of the latest eligible WINDFOR revision")
    forecast_mw: float | None
    actual_mw: float | None
    signed_error_mw: float | None = Field(description="Forecast minus actual, MW")


class TimeseriesResponse(BaseModel):
    decision_cutoff_local: str
    timezone: str = "Europe/London"
    refreshed_at: str
    sources: Sources
    warnings: list[str]
    intervals: list[IntervalResponse]


class SummaryResponse(BaseModel):
    first_decision_date: str = "2026-01-01"
    last_decision_date: str = "2026-01-31"
    first_delivery_date: str = "2026-01-02"
    last_delivery_date: str = "2026-02-01"
    decision_cutoff_local: str
    timezone: str = "Europe/London"
    expected_intervals: int
    refreshed_at: str
    source_rows: dict[str, int]
    sources: Sources
    accuracy: AccuracyResponse
    warnings: list[str]
