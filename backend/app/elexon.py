"""The only upstream data sources used by the analysis."""

import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx


BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
FUELHH_URL = f"{BASE_URL}/FUELHH/stream"
WINDFOR_URL = f"{BASE_URL}/WINDFOR/stream"


class ElexonError(Exception):
    pass


def utc_string(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def each_day(first: date, last: date):
    day = first
    while day <= last:
        yield day
        day += timedelta(days=1)


class ElexonClient:
    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))
        self.owns_client = client is None

    def close(self) -> None:
        if self.owns_client:
            self.client.close()

    def _get(self, url: str, params: dict[str, str]) -> list[dict[str, Any]]:
        for attempt in range(4):
            try:
                response = self.client.get(url, params=params, headers={"Accept": "application/json"})
                if response.status_code == 429 or 500 <= response.status_code <= 599:
                    if attempt < 3:
                        retry_after = response.headers.get("Retry-After", "")
                        delay = min(float(retry_after), 30) if retry_after.isdigit() else 2**attempt
                        time.sleep(delay)
                        continue
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
                    raise ElexonError(f"Unexpected JSON shape from {url}; expected an array of records")
                return data
            except httpx.TransportError as exc:
                if attempt == 3:
                    raise ElexonError(f"Elexon request timed out or failed: {url}: {exc}") from exc
                time.sleep(2**attempt)
            except (httpx.HTTPStatusError, ValueError) as exc:
                raise ElexonError(f"Elexon request failed: {url}: {exc}") from exc
        raise ElexonError(f"Elexon request failed after retries: {url}")

    def actual_day(self, day: date) -> list[dict[str, Any]]:
        return self._get(FUELHH_URL, {
            "settlementDateFrom": day.isoformat(),
            "settlementDateTo": day.isoformat(),
            "fuelType": "WIND",
        })

    def forecast_publish_day(self, day: date) -> list[dict[str, Any]]:
        start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        return self._get(WINDFOR_URL, {
            "publishDateTimeFrom": utc_string(start),
            "publishDateTimeTo": utc_string(start + timedelta(days=1)),
        })
