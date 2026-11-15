from __future__ import annotations

import json

import pytest

from weather_digest.config import ConfigError, load_config


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def test_load_yaml_config(tmp_path):
    cfg = _write(
        tmp_path / "sites.yaml",
        """
forecast_days: 2
thresholds:
  max_wind_kmh: 30
  max_precip_mm: 5
sites:
  - name: Test Site
    latitude: 10.0
    longitude: 20.0
""",
    )
    config = load_config(cfg)
    assert len(config.sites) == 1
    assert config.sites[0].name == "Test Site"
    assert config.forecast_days == 2
    assert config.thresholds.max_wind_kmh == 30
    assert config.thresholds.max_precip_mm == 5


def test_load_json_config(tmp_path):
    data = {
        "sites": [{"name": "JSON Site", "latitude": 1.0, "longitude": 2.0}],
    }
    cfg = _write(tmp_path / "sites.json", json.dumps(data))
    config = load_config(cfg)
    assert config.sites[0].name == "JSON Site"
    # Defaults fill in when thresholds are omitted.
    assert config.thresholds.max_wind_kmh == 40.0


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.yaml")


def test_empty_sites_rejected(tmp_path):
    cfg = _write(tmp_path / "sites.yaml", "sites: []")
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_bad_latitude_rejected(tmp_path):
    cfg = _write(
        tmp_path / "sites.yaml",
        "sites:\n  - name: Bad\n    latitude: 999\n    longitude: 0\n",
    )
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_unknown_extension_rejected(tmp_path):
    cfg = _write(tmp_path / "sites.txt", "sites: []")
    with pytest.raises(ConfigError):
        load_config(cfg)
