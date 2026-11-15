from __future__ import annotations

import pytest

from weather_digest.client import (
    WeatherAPIError,
    fetch_all,
    fetch_site,
    parse_daily,
)
from weather_digest.config import Site


def test_parse_daily_builds_rows(sample_payload):
    rows = parse_daily("London Yard", sample_payload)
    assert len(rows) == 2
    first = rows[0]
    assert first.site_name == "London Yard"
    assert first.date == "2026-11-15"
    assert first.temp_max_c == 12.4
    assert first.wind_max_kmh == 18.0
    assert rows[1].precipitation_mm == 22.0


def test_parse_daily_handles_missing_column(sample_payload):
    # Drop a column and confirm the parser fills None instead of crashing.
    del sample_payload["daily"]["windspeed_10m_max"]
    rows = parse_daily("Partial", sample_payload)
    assert rows[0].wind_max_kmh is None
    assert rows[0].temp_max_c == 12.4


def test_parse_daily_rejects_missing_daily_block():
    with pytest.raises(WeatherAPIError):
        parse_daily("Broken", {"latitude": 1.0})


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._payload


class _FakeSession:
    """Stands in for requests.Session. Records the last call and returns canned data."""

    def __init__(self, payload):
        self._payload = payload
        self.last_url = None
        self.last_params = None

    def get(self, url, params=None, timeout=None):
        self.last_url = url
        self.last_params = params
        return _FakeResponse(self._payload)


def test_fetch_site_uses_injected_session(sample_payload):
    session = _FakeSession(sample_payload)
    site = Site(name="London Yard", latitude=51.5, longitude=-0.12)

    rows = fetch_site(site, forecast_days=2, session=session)

    assert len(rows) == 2
    assert session.last_url.endswith("/v1/forecast")
    assert session.last_params["latitude"] == 51.5
    assert session.last_params["forecast_days"] == 2


def test_fetch_all_iterates_sites(sample_payload):
    session = _FakeSession(sample_payload)
    sites = [
        Site(name="A", latitude=1.0, longitude=2.0),
        Site(name="B", latitude=3.0, longitude=4.0),
    ]
    rows = fetch_all(sites, forecast_days=2, session=session)
    # Two sites, two days each.
    assert len(rows) == 4
    assert {r.site_name for r in rows} == {"A", "B"}


def test_fetch_site_wraps_request_errors():
    import requests

    class _Boom:
        def get(self, *a, **k):
            raise requests.ConnectionError("no network")

    site = Site(name="X", latitude=0.0, longitude=0.0)
    with pytest.raises(WeatherAPIError):
        fetch_site(site, session=_Boom())
