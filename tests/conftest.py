"""Shared fixtures. Nothing here touches the network."""

from __future__ import annotations

import pytest

from weather_digest.client import DailyForecast


@pytest.fixture
def sample_payload():
    """A trimmed Open-Meteo-shaped payload for one site, two days."""

    return {
        "latitude": 51.5,
        "longitude": -0.12,
        "daily": {
            "time": ["2026-11-15", "2026-11-16"],
            "temperature_2m_max": [12.4, 9.1],
            "temperature_2m_min": [6.2, 3.0],
            "precipitation_sum": [0.5, 22.0],
            "windspeed_10m_max": [18.0, 55.0],
        },
    }


@pytest.fixture
def calm_forecast():
    return DailyForecast(
        site_name="Calm Site",
        date="2026-11-15",
        temp_max_c=20.0,
        temp_min_c=10.0,
        precipitation_mm=1.0,
        wind_max_kmh=15.0,
    )


@pytest.fixture
def stormy_forecast():
    return DailyForecast(
        site_name="Stormy Site",
        date="2026-11-16",
        temp_max_c=18.0,
        temp_min_c=9.0,
        precipitation_mm=25.0,
        wind_max_kmh=60.0,
    )
