"""Open-Meteo API client and response parsing.

Open-Meteo is free and needs no key, which is why I picked it for a portfolio
piece. I keep the HTTP call and the parsing in separate functions so the parser
can be tested without the network.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from .config import Site

API_URL = "https://api.open-meteo.com/v1/forecast"

# The daily fields I ask Open-Meteo for. Kept here so the parser and the request
# stay in step.
DAILY_FIELDS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "windspeed_10m_max",
]


class WeatherAPIError(RuntimeError):
    """Raised when the API call fails or the response is not shaped as expected."""


@dataclass(frozen=True)
class DailyForecast:
    """One day of forecast for one site."""

    site_name: str
    date: str
    temp_max_c: float | None
    temp_min_c: float | None
    precipitation_mm: float | None
    wind_max_kmh: float | None


def build_params(site: Site, forecast_days: int) -> dict:
    return {
        "latitude": site.latitude,
        "longitude": site.longitude,
        "daily": ",".join(DAILY_FIELDS),
        "timezone": "auto",
        "forecast_days": forecast_days,
    }


def parse_daily(site_name: str, payload: dict) -> list[DailyForecast]:
    """Turn a raw Open-Meteo payload into a list of DailyForecast rows.

    This is pure and takes a dict, so tests can feed it a fixture.
    """

    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise WeatherAPIError(f"No 'daily' block in the response for {site_name}.")

    dates = daily.get("time")
    if not isinstance(dates, list) or not dates:
        raise WeatherAPIError(f"No dates returned for {site_name}.")

    def column(key: str) -> list:
        values = daily.get(key)
        if not isinstance(values, list) or len(values) != len(dates):
            # Missing or mismatched column: fill with None so one bad field does
            # not sink the whole site.
            return [None] * len(dates)
        return values

    temp_max = column("temperature_2m_max")
    temp_min = column("temperature_2m_min")
    precip = column("precipitation_sum")
    wind = column("windspeed_10m_max")

    rows: list[DailyForecast] = []
    for i, date in enumerate(dates):
        rows.append(
            DailyForecast(
                site_name=site_name,
                date=str(date),
                temp_max_c=_as_float(temp_max[i]),
                temp_min_c=_as_float(temp_min[i]),
                precipitation_mm=_as_float(precip[i]),
                wind_max_kmh=_as_float(wind[i]),
            )
        )
    return rows


def _as_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_site(
    site: Site,
    forecast_days: int = 1,
    *,
    session: requests.Session | None = None,
    timeout: float = 20.0,
) -> list[DailyForecast]:
    """Call Open-Meteo for one site and return parsed rows.

    I pass a session in from the caller so every site reuses one connection, and
    so tests can hand me a fake.
    """

    http = session or requests
    try:
        response = http.get(
            API_URL, params=build_params(site, forecast_days), timeout=timeout
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise WeatherAPIError(f"Request failed for {site.name}: {exc}") from exc
    except ValueError as exc:
        raise WeatherAPIError(f"Bad JSON for {site.name}: {exc}") from exc

    return parse_daily(site.name, payload)


def fetch_all(
    sites: list[Site],
    forecast_days: int = 1,
    *,
    session: requests.Session | None = None,
) -> list[DailyForecast]:
    """Fetch every site. One session, reused, so this stays light."""

    owns_session = session is None
    http_session = session or requests.Session()
    try:
        rows: list[DailyForecast] = []
        for site in sites:
            rows.extend(fetch_site(site, forecast_days, session=http_session))
        return rows
    finally:
        if owns_session:
            http_session.close()
