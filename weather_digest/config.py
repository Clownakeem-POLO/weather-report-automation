"""Config loading and validation.

A config file lists the sites I want forecasts for and the thresholds that decide
when outdoor work should stop. I keep the shape simple on purpose: a list of
sites, each with a name and coordinates, plus a thresholds block.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class ConfigError(ValueError):
    """Raised when a config file is missing required data or is malformed."""


@dataclass(frozen=True)
class Site:
    """One operational site I want a forecast for."""

    name: str
    latitude: float
    longitude: float

    def validate(self) -> None:
        if not self.name or not str(self.name).strip():
            raise ConfigError("A site is missing a name.")
        if not (-90.0 <= self.latitude <= 90.0):
            raise ConfigError(
                f"Site '{self.name}' has latitude {self.latitude}, which is out of range."
            )
        if not (-180.0 <= self.longitude <= 180.0):
            raise ConfigError(
                f"Site '{self.name}' has longitude {self.longitude}, which is out of range."
            )


@dataclass(frozen=True)
class Thresholds:
    """The limits that flag a site as unsafe for outdoor work.

    Defaults are deliberately conservative placeholders. Every operation should
    set its own numbers in the config file.
    """

    max_wind_kmh: float = 40.0
    max_precip_mm: float = 10.0
    min_temp_c: float = -10.0
    max_temp_c: float = 40.0


@dataclass(frozen=True)
class Config:
    sites: list[Site] = field(default_factory=list)
    thresholds: Thresholds = field(default_factory=Thresholds)
    forecast_days: int = 1

    def validate(self) -> None:
        if not self.sites:
            raise ConfigError("The config has no sites. Add at least one.")
        for site in self.sites:
            site.validate()
        if not (1 <= self.forecast_days <= 16):
            raise ConfigError(
                f"forecast_days is {self.forecast_days}; Open-Meteo supports 1 to 16."
            )


def _load_raw(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(text)
    elif path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        raise ConfigError(
            f"I do not know how to read '{path.suffix}'. Use .yaml, .yml or .json."
        )
    if not isinstance(data, dict):
        raise ConfigError("The config file should be a mapping at the top level.")
    return data


def load_config(path: str | Path) -> Config:
    """Read and validate a config file, returning a Config.

    I raise ConfigError with a plain message when something is wrong, so the CLI
    can print it without a stack trace.
    """

    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    raw = _load_raw(path)

    raw_sites = raw.get("sites")
    if not isinstance(raw_sites, list):
        raise ConfigError("The config needs a 'sites' list.")

    sites: list[Site] = []
    for entry in raw_sites:
        if not isinstance(entry, dict):
            raise ConfigError(f"Each site should be a mapping, got: {entry!r}")
        try:
            site = Site(
                name=str(entry["name"]),
                latitude=float(entry["latitude"]),
                longitude=float(entry["longitude"]),
            )
        except KeyError as exc:
            raise ConfigError(f"A site is missing the field {exc}.") from exc
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"A site has a bad coordinate: {exc}") from exc
        sites.append(site)

    raw_thresholds = raw.get("thresholds") or {}
    if not isinstance(raw_thresholds, dict):
        raise ConfigError("'thresholds' should be a mapping if present.")
    try:
        thresholds = Thresholds(
            max_wind_kmh=float(raw_thresholds.get("max_wind_kmh", Thresholds.max_wind_kmh)),
            max_precip_mm=float(raw_thresholds.get("max_precip_mm", Thresholds.max_precip_mm)),
            min_temp_c=float(raw_thresholds.get("min_temp_c", Thresholds.min_temp_c)),
            max_temp_c=float(raw_thresholds.get("max_temp_c", Thresholds.max_temp_c)),
        )
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"A threshold value is not a number: {exc}") from exc

    config = Config(
        sites=sites,
        thresholds=thresholds,
        forecast_days=int(raw.get("forecast_days", 1)),
    )
    config.validate()
    return config
