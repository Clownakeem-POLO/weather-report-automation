"""Command line entry point.

Usage:
    python -m weather_digest run --config sites.yaml --out ./reports
    python -m weather_digest run --config sites.yaml --dry-run

I keep the CLI thin: it wires config, client, report and emailer together and
prints a short summary. The real work lives in the other modules.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .client import WeatherAPIError, fetch_all
from .config import ConfigError, load_config
from .emailer import SmtpSettings, send_report
from .report import evaluate_all, generate_reports, render_html, report_date_stamp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="weather_digest",
        description="Build a daily operations weather digest from Open-Meteo.",
    )
    parser.add_argument("--version", action="version", version=f"weather_digest {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Fetch forecasts and write the report.")
    run.add_argument(
        "--config",
        required=True,
        help="Path to the sites config file (YAML or JSON).",
    )
    run.add_argument(
        "--out",
        default="./reports",
        help="Directory to write report files into (default: ./reports).",
    )
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and build the report but never email it.",
    )
    run.add_argument(
        "--no-email",
        action="store_true",
        help="Alias for --dry-run: write files only.",
    )
    return parser


def run_command(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    print(f"Loaded {len(config.sites)} site(s) from {args.config}.")

    try:
        forecasts = fetch_all(config.sites, config.forecast_days)
    except WeatherAPIError as exc:
        print(f"Forecast error: {exc}", file=sys.stderr)
        return 3

    rows = evaluate_all(forecasts, config.thresholds)
    stamp = report_date_stamp()

    out_dir = Path(args.out)
    result = generate_reports(rows, out_dir, stamp)

    print(f"Wrote {result.excel_path}")
    print(f"Wrote {result.html_path}")
    print(
        f"{result.stop_count} of {result.total} site-days flagged to stop work."
    )

    skip_email = args.dry_run or args.no_email
    if skip_email:
        print("Dry run: skipping email.")
        return 0

    settings = SmtpSettings.from_env()
    if settings is None:
        print("SMTP environment variables not set: skipping email, files saved locally.")
        return 0

    try:
        send_report(
            settings,
            subject=f"Operations weather digest {stamp}",
            html_body=render_html(rows, stamp),
            attachments=[result.excel_path, result.html_path],
        )
    except Exception as exc:  # noqa: BLE001 - surface any SMTP failure plainly
        print(f"Email failed: {exc}. Files are still saved locally.", file=sys.stderr)
        return 4

    print(f"Emailed the report to {len(settings.recipients)} recipient(s).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return run_command(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
