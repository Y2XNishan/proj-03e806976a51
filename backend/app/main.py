import os
from datetime import date
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .analysis import FIRST_DECISION, LAST_DECISION, DataIntegrityError, analyze, calculate_accuracy
from .cache import CacheUnavailable, cache_path, load
from .models import AccuracyResponse, SummaryResponse, TimeseriesResponse
from .snapshot_store import MANIFEST_PATH, load_snapshot


app = FastAPI(title="WindScope Forecast API", version="0.1.0")

default_origins = "" if os.getenv("VERCEL") else "http://localhost:5173,http://127.0.0.1:5173"
origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", default_origins).split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET"], allow_headers=["*"])


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(CacheUnavailable)
def cache_error(_request, exc: CacheUnavailable) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(DataIntegrityError)
def data_error(_request, exc: DataIntegrityError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": f"Cached Elexon data failed validation: {exc}"})


@lru_cache(maxsize=2)
def _analyzed_snapshot(path: str, modified_ns: int, cutoff: str, source_kind: str = "sqlite"):
    loader = load_snapshot if source_kind == "bundle" else load
    metadata, forecasts, actuals = loader(Path(path))
    try:
        return analyze(metadata, forecasts, actuals, cutoff)
    except ValueError as exc:
        raise CacheUnavailable(f"Invalid cutoff configuration: {exc}") from exc


def snapshot():
    if os.getenv("ELEXON_CACHE_PATH"):
        path, source_kind = cache_path(), "sqlite"
    elif MANIFEST_PATH.is_file():
        path, source_kind = MANIFEST_PATH, "bundle"
    elif os.getenv("VERCEL") or os.getenv("SNAPSHOT_REQUIRED") == "1":
        raise CacheUnavailable("Bundled historical snapshot is missing from this deployment")
    else:
        path, source_kind = cache_path(), "sqlite"
    if not path.exists():
        raise CacheUnavailable("Elexon cache is absent; run `python -m app.refresh` from backend first")
    return _analyzed_snapshot(str(path), path.stat().st_mtime_ns,
                              os.getenv("DAY_AHEAD_CUTOFF_LOCAL", "12:00"), source_kind)


@app.get("/api/summary", response_model=SummaryResponse)
def summary():
    result = snapshot()
    metadata = result["metadata"]
    return {
        "decision_cutoff_local": result["cutoff_local"],
        "expected_intervals": len(result["intervals"]),
        "refreshed_at": metadata["refreshed_at"],
        "source_rows": {"WINDFOR": metadata["forecast_rows"], "FUELHH": metadata["actual_rows"]},
        "sources": result["sources"], "accuracy": result["accuracy"], "warnings": result["warnings"],
    }


@app.get("/api/timeseries", response_model=TimeseriesResponse)
def timeseries(decision_date: date | None = None):
    if decision_date is not None and not FIRST_DECISION <= decision_date <= LAST_DECISION:
        raise HTTPException(status_code=400, detail="decision_date must be from 2026-01-01 through 2026-01-31")
    result = snapshot()
    intervals = result["intervals"]
    if decision_date is not None:
        intervals = [row for row in intervals if row["decision_date"] == decision_date.isoformat()]
    return {"decision_cutoff_local": result["cutoff_local"], "refreshed_at": result["metadata"]["refreshed_at"],
            "sources": result["sources"], "warnings": result["warnings"], "intervals": intervals}


@app.get("/api/accuracy", response_model=AccuracyResponse)
def accuracy(decision_date_from: date | None = None, decision_date_to: date | None = None):
    if (decision_date_from is None) != (decision_date_to is None):
        raise HTTPException(status_code=400, detail="Provide both decision_date_from and decision_date_to")
    if decision_date_from is not None:
        if not FIRST_DECISION <= decision_date_from <= decision_date_to <= LAST_DECISION:
            raise HTTPException(status_code=400, detail="Decision date range must be within 2026-01-01 through 2026-01-31, with from <= to")
        intervals = [row for row in snapshot()["intervals"]
                     if decision_date_from.isoformat() <= row["decision_date"] <= decision_date_to.isoformat()]
        return calculate_accuracy(intervals)
    return snapshot()["accuracy"]

