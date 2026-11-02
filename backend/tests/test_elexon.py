"""HTTP fixtures verify the exact two dataset paths and query parameters."""

from datetime import date

import httpx
import pytest

from app import elexon


def test_stream_requests_use_documented_filters():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=[])

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        client = elexon.ElexonClient(http)
        assert client.actual_day(date(2026, 1, 2)) == []
        assert client.forecast_publish_day(date(2026, 1, 1)) == []
    assert requests[0].url.path == "/bmrs/api/v1/datasets/FUELHH/stream"
    assert dict(requests[0].url.params) == {
        "settlementDateFrom": "2026-01-02", "settlementDateTo": "2026-01-02", "fuelType": "WIND"
    }
    assert requests[1].url.path == "/bmrs/api/v1/datasets/WINDFOR/stream"
    assert dict(requests[1].url.params) == {
        "publishDateTimeFrom": "2026-01-01T00:00:00Z", "publishDateTimeTo": "2026-01-02T00:00:00Z"
    }


def test_retry_rate_limit_and_reject_bad_shape(monkeypatch):
    monkeypatch.setattr(elexon.time, "sleep", lambda _: None)
    calls = 0

    def respond(_request):
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "1"}) if calls == 1 else httpx.Response(200, json=[])

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        assert elexon.ElexonClient(http).actual_day(date(2026, 1, 2)) == []
    assert calls == 2

    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"data": []}))) as http:
        with pytest.raises(elexon.ElexonError, match="Unexpected JSON shape"):
            elexon.ElexonClient(http).forecast_publish_day(date(2026, 1, 1))
