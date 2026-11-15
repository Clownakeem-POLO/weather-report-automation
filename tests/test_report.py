from __future__ import annotations

from openpyxl import load_workbook

from weather_digest.client import DailyForecast
from weather_digest.config import Thresholds
from weather_digest.report import (
    HEADERS,
    evaluate_all,
    evaluate_row,
    generate_reports,
    render_html,
)

THRESHOLDS = Thresholds(
    max_wind_kmh=40.0, max_precip_mm=10.0, min_temp_c=-10.0, max_temp_c=40.0
)


def test_calm_site_is_ok(calm_forecast):
    row = evaluate_row(calm_forecast, THRESHOLDS)
    assert row.stop_work is False
    assert row.status == "OK"
    assert row.reasons == []


def test_stormy_site_flags_wind_and_rain(stormy_forecast):
    row = evaluate_row(stormy_forecast, THRESHOLDS)
    assert row.stop_work is True
    assert row.status == "STOP"
    # Both the wind and the rain limit are crossed.
    assert any("wind" in r for r in row.reasons)
    assert any("rain" in r for r in row.reasons)


def test_cold_and_heat_flags():
    cold = DailyForecast("Cold", "2026-01-01", 2.0, -15.0, 0.0, 5.0)
    hot = DailyForecast("Hot", "2026-07-01", 45.0, 25.0, 0.0, 5.0)
    assert evaluate_row(cold, THRESHOLDS).stop_work is True
    assert any("cold" in r for r in evaluate_row(cold, THRESHOLDS).reasons)
    assert any("heat" in r for r in evaluate_row(hot, THRESHOLDS).reasons)


def test_missing_values_do_not_flag():
    # A row with all None should not be flagged, since nothing crosses a limit.
    unknown = DailyForecast("Unknown", "2026-05-05", None, None, None, None)
    assert evaluate_row(unknown, THRESHOLDS).stop_work is False


def test_render_html_contains_summary(calm_forecast, stormy_forecast):
    rows = evaluate_all([calm_forecast, stormy_forecast], THRESHOLDS)
    html = render_html(rows, "2026-11-15")
    assert "Operations weather digest" in html
    assert "Stormy Site" in html
    assert "STOP" in html
    for header in HEADERS:
        assert header in html


def test_generate_reports_writes_both_files(tmp_path, calm_forecast, stormy_forecast):
    rows = evaluate_all([calm_forecast, stormy_forecast], THRESHOLDS)
    result = generate_reports(rows, tmp_path, stamp="2026-11-15")

    assert result.excel_path.exists()
    assert result.html_path.exists()
    assert result.total == 2
    assert result.stop_count == 1

    # The Excel file has a header row plus one row per forecast.
    wb = load_workbook(result.excel_path)
    ws = wb.active
    assert ws.max_row == 3
    assert [c.value for c in ws[1]] == HEADERS
