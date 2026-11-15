"""Transform forecasts into flagged rows and write Excel and HTML reports.

The flagging logic is the part that matters for operations: given thresholds, is
this site safe to work at on this day? Everything else is presentation.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from .client import DailyForecast
from .config import Thresholds

# Column headers, shared by the Excel sheet and the HTML table.
HEADERS = [
    "Site",
    "Date",
    "Temp max (C)",
    "Temp min (C)",
    "Precip (mm)",
    "Wind max (km/h)",
    "Work status",
    "Reasons",
]


@dataclass(frozen=True)
class FlaggedRow:
    """A forecast row plus the work-stoppage verdict I derived from it."""

    forecast: DailyForecast
    stop_work: bool
    reasons: list[str]

    @property
    def status(self) -> str:
        return "STOP" if self.stop_work else "OK"


def evaluate_row(forecast: DailyForecast, thresholds: Thresholds) -> FlaggedRow:
    """Decide whether conditions would stop outdoor work at one site on one day.

    I collect every reason rather than stopping at the first, because an ops lead
    wants the full picture, not just the first tripped limit.
    """

    reasons: list[str] = []

    if forecast.wind_max_kmh is not None and forecast.wind_max_kmh > thresholds.max_wind_kmh:
        reasons.append(
            f"wind {forecast.wind_max_kmh:.0f} km/h over limit {thresholds.max_wind_kmh:.0f}"
        )
    if (
        forecast.precipitation_mm is not None
        and forecast.precipitation_mm > thresholds.max_precip_mm
    ):
        reasons.append(
            f"rain {forecast.precipitation_mm:.1f} mm over limit {thresholds.max_precip_mm:.1f}"
        )
    if forecast.temp_max_c is not None and forecast.temp_max_c > thresholds.max_temp_c:
        reasons.append(
            f"heat {forecast.temp_max_c:.0f}C over limit {thresholds.max_temp_c:.0f}C"
        )
    if forecast.temp_min_c is not None and forecast.temp_min_c < thresholds.min_temp_c:
        reasons.append(
            f"cold {forecast.temp_min_c:.0f}C under limit {thresholds.min_temp_c:.0f}C"
        )

    return FlaggedRow(forecast=forecast, stop_work=bool(reasons), reasons=reasons)


def evaluate_all(
    forecasts: list[DailyForecast], thresholds: Thresholds
) -> list[FlaggedRow]:
    return [evaluate_row(f, thresholds) for f in forecasts]


def _cell_values(row: FlaggedRow) -> list:
    f = row.forecast
    return [
        f.site_name,
        f.date,
        f.temp_max_c,
        f.temp_min_c,
        f.precipitation_mm,
        f.wind_max_kmh,
        row.status,
        "; ".join(row.reasons),
    ]


def report_date_stamp(today: date | None = None) -> str:
    return (today or date.today()).isoformat()


def write_excel(rows: list[FlaggedRow], out_path: Path) -> Path:
    """Write the flagged rows to an .xlsx file, STOP rows shaded red."""

    wb = Workbook()
    ws = wb.active
    ws.title = "Weather digest"

    header_font = Font(bold=True)
    for col, header in enumerate(HEADERS, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font

    stop_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

    for r, row in enumerate(rows, start=2):
        for c, value in enumerate(_cell_values(row), start=1):
            cell = ws.cell(row=r, column=c, value=value)
            if row.stop_work:
                cell.fill = stop_fill

    # Rough auto-width so the file opens readable.
    for col in range(1, len(HEADERS) + 1):
        letter = ws.cell(row=1, column=col).column_letter
        longest = max(
            [len(str(HEADERS[col - 1]))]
            + [len(str(_cell_values(row)[col - 1])) for row in rows],
            default=10,
        )
        ws.column_dimensions[letter].width = min(longest + 2, 40)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path


def render_html(rows: list[FlaggedRow], stamp: str) -> str:
    """Build a small self-contained HTML summary string."""

    stop_count = sum(1 for row in rows if row.stop_work)
    total = len(rows)

    header_cells = "".join(f"<th>{html.escape(h)}</th>" for h in HEADERS)

    body_rows = []
    for row in rows:
        css = "stop" if row.stop_work else "ok"
        cells = []
        for value in _cell_values(row):
            text = "" if value is None else str(value)
            cells.append(f"<td>{html.escape(text)}</td>")
        body_rows.append(f'<tr class="{css}">{"".join(cells)}</tr>')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Operations weather digest {html.escape(stamp)}</title>
<style>
  body {{ font-family: system-ui, Arial, sans-serif; margin: 2rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.4rem; }}
  .summary {{ margin: 1rem 0; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #d0d0d0; padding: 6px 10px; text-align: left; font-size: 0.9rem; }}
  th {{ background: #f0f0f0; }}
  tr.stop td {{ background: #fdecea; }}
  tr.ok td {{ background: #ffffff; }}
  .badge-stop {{ color: #b3261e; font-weight: bold; }}
  .badge-ok {{ color: #1e7d34; font-weight: bold; }}
</style>
</head>
<body>
<h1>Operations weather digest</h1>
<p class="summary">Report date {html.escape(stamp)}.
<span class="badge-stop">{stop_count}</span> of {total} site-days flagged to stop work,
<span class="badge-ok">{total - stop_count}</span> clear.</p>
<table>
<thead><tr>{header_cells}</tr></thead>
<tbody>
{chr(10).join(body_rows)}
</tbody>
</table>
<p class="summary">Forecast data from Open-Meteo. Thresholds are set in the config file.</p>
</body>
</html>
"""


def write_html(rows: list[FlaggedRow], out_path: Path, stamp: str) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_html(rows, stamp), encoding="utf-8")
    return out_path


@dataclass(frozen=True)
class ReportResult:
    excel_path: Path
    html_path: Path
    stop_count: int
    total: int


def generate_reports(
    rows: list[FlaggedRow], out_dir: Path, stamp: str | None = None
) -> ReportResult:
    """Write both files into out_dir with a dated name and return their paths."""

    stamp = stamp or report_date_stamp()
    out_dir = Path(out_dir)
    excel_path = out_dir / f"weather-digest-{stamp}.xlsx"
    html_path = out_dir / f"weather-digest-{stamp}.html"

    write_excel(rows, excel_path)
    write_html(rows, html_path, stamp)

    return ReportResult(
        excel_path=excel_path,
        html_path=html_path,
        stop_count=sum(1 for row in rows if row.stop_work),
        total=len(rows),
    )
