# Weather Report Automation

A small automation that builds a daily weather digest for a company running
field or site operations. It reads a list of sites, pulls the forecast for each
one, and writes a report that tells an ops lead where the weather would stop
outdoor work that day. It can email the report, or just save it locally.

I built this as a portfolio piece to show how I put reliable automation
together: a packaged CLI, config driven behaviour, mocked tests, and CI that
runs on a schedule.

## Why

If you run crews across several sites, someone has to check the weather for each
one every morning and decide what is safe to do. That is a chore and it is easy
to get wrong. This tool does the checking, applies the same rules every time,
and hands back one dated report. The rules live in a config file, so the people
who know the crews can set the limits without touching code.

## What it does

1. Reads a list of sites (name plus latitude and longitude) from a YAML or JSON
   config file.
2. Fetches the daily forecast for each site from the
   [Open-Meteo API](https://open-meteo.com/). Open-Meteo is free and needs no
   API key, which keeps this easy to run anywhere. It pulls daily temperature
   max and min, total precipitation, and max wind speed.
3. Applies your work-stoppage thresholds and flags any site-day where the wind,
   rain, heat, or cold crosses a limit.
4. Writes two files into a dated report: an Excel workbook (`.xlsx`) with STOP
   rows shaded red, and a clean HTML summary.
5. Optionally emails the report over SMTP. If the SMTP environment variables are
   not set, it skips emailing and just leaves the files on disk.

## Sample output

A committed example sits in [`examples/`](examples/): `sample-report.html` and
`sample-report.xlsx`, generated from the four example sites in `sites.yaml`.

The HTML summary opens with a line like:

> Report date 2026-11-15. 1 of 4 site-days flagged to stop work, 3 clear.

Then a table, one row per site per day:

| Site | Date | Temp max (C) | Temp min (C) | Precip (mm) | Wind max (km/h) | Work status | Reasons |
| --- | --- | --- | --- | --- | --- | --- | --- |
| London Yard (example) | 2026-11-15 | 12.4 | 6.2 | 0.5 | 18 | OK | |
| Rotterdam Port (example) | 2026-11-15 | 11.0 | 7.1 | 14.2 | 44 | STOP | wind 44 km/h over limit 40; rain 14.2 mm over limit 10.0 |

Rows flagged STOP are shaded red in the Excel file so they stand out at a glance.
(The numbers above are illustrative. Your run shows live forecast data.)

## Install

You need Python 3.10 or newer.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Run

```bash
# Fetch forecasts and write the report into ./reports
python -m weather_digest run --config sites.yaml --out ./reports

# Build the report but never email it, whatever the environment says
python -m weather_digest run --config sites.yaml --dry-run
```

The CLI prints the files it wrote and how many site-days were flagged. Exit code
is 0 on success, non-zero on a config or forecast error, so it fits into a
pipeline.

## Configuration

The config file lists your sites and your thresholds. See `sites.yaml` for a
working example. The shape:

```yaml
forecast_days: 1          # 1 to 16 days ahead

thresholds:               # outdoor work stops when any limit is crossed
  max_wind_kmh: 40
  max_precip_mm: 10
  min_temp_c: -10
  max_temp_c: 40

sites:
  - name: "London Yard"
    latitude: 51.5072
    longitude: -0.1276
```

JSON works too, with the same keys. Thresholds are optional; sensible defaults
fill in when you leave them out, but I recommend setting your own.

## Emailing

Emailing is off unless you set SMTP credentials in the environment. Copy
`.env.example` to `.env`, fill it in, and load it before running (for example
with `set -a; source .env; set +a` on bash, or your own secrets manager). The
variables:

- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USE_TLS`
- `SMTP_USERNAME`, `SMTP_PASSWORD`
- `SMTP_FROM` (optional, defaults to the username)
- `SMTP_TO` (comma-separated recipients)

Credentials are never hardcoded and never committed. If any required variable is
missing, the tool says so and saves the files locally instead of failing.

## How scheduling works

There are two GitHub Actions workflows in `.github/workflows/`:

- `ci.yml` runs the test suite on every push and pull request, across Python
  3.10 to 3.12. The tests mock the API, so CI never hits the network.
- `scheduled-report.yml` runs the CLI on a daily cron (06:00 UTC) in `--dry-run`
  mode and uploads the report as a build artifact. Dry run means it fetches real
  forecasts but never tries to email, so the scheduled job needs no secrets.
  That makes it safe to leave running in a public repo as a live demo of the
  automation. To make it email a real team, drop `--dry-run` and wire the SMTP
  values in as repository secrets.

You could run the same command from cron, Windows Task Scheduler, or any job
runner. It is just `python -m weather_digest run ...`.

## Tests

```bash
pytest
```

The suite covers config loading and validation, the Open-Meteo response parser,
the work-stoppage flagging logic, report generation to a temp directory, and the
SMTP settings and message building. None of it touches the network: the HTTP
calls are replaced with a fake session, and the parser is fed fixture payloads.

## Limitations (honest ones)

- The flagging is a simple per-day threshold check. It uses daily aggregates, so
  a short violent squall can be hidden inside an otherwise calm day. For
  safety-critical calls, treat this as a first pass, not the last word.
- Open-Meteo forecasts are models, not guarantees. Accuracy drops the further
  ahead you look.
- There is no retry or backoff on the API call yet. If Open-Meteo is down, the
  run fails with a clear error rather than producing a partial report.
- Timezone handling uses Open-Meteo's `timezone=auto`, so each site's day is in
  its own local time. If you need everything in one timezone, that is a change to
  make in `client.py`.
- Email delivery depends on your SMTP provider. The tool reports a send failure
  but still leaves the files on disk.

## Project layout

```
weather_digest/        the package
  config.py            load and validate the sites config
  client.py            Open-Meteo calls and response parsing
  report.py            flagging logic, Excel and HTML output
  emailer.py           optional SMTP sending
  cli.py               argparse command line
  __main__.py          python -m weather_digest
tests/                 pytest suite, no network
examples/              a committed sample report
.github/workflows/     CI and the scheduled run
sites.yaml             example config with real cities
```

## License

MIT. See [LICENSE](LICENSE).
