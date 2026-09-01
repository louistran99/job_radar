#!/usr/bin/env python3
"""CLI entry point for the daily ATS job monitor."""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from src.clients.http import ATSClientError, BoardNotFoundError, make_session
from src.config import (
    DEFAULT_JOBS_YAML,
    JobsConfig,
    enabled_companies,
    load_jobs_config,
    resolve_config_path,
)
from src.fetch import Fetcher, LiveFetcher
from src.match import job_matches
from src.models import Job
from src.report import render_report, stdout_summary, write_report
from src.snapshot import (
    diff_snapshots,
    load_snapshot,
    merge_current_with_previous,
    save_snapshot,
)
from src.validate import validate_companies

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "output"
DEFAULT_SNAPSHOT = DEFAULT_OUTPUT_DIR / "snapshot.json"
DEFAULT_REPORT = DEFAULT_OUTPUT_DIR / "report.md"

logger = logging.getLogger(__name__)


def run(
    config: JobsConfig,
    fetcher: Fetcher,
    snapshot_path: Path,
    report_path: Path,
    *,
    validate_only: bool = False,
    delay_seconds: float | None = None,
) -> int:
    companies = enabled_companies(config)
    if not companies:
        logger.error("No enabled companies to fetch. Check config/jobs.yaml.")
        return 1

    delay = config.delay_seconds if delay_seconds is None else delay_seconds

    if validate_only:
        valid, skipped = validate_companies(fetcher, companies)
        for company in valid:
            logger.info("OK %s (%s/%s)", company.name, company.ats, company.slug)
        logger.info("Valid: %s  Skipped: %s", len(valid), len(skipped))
        return 0

    previous = load_snapshot(snapshot_path)
    matched: dict[str, Job] = {}
    failed_keys: set[tuple[str, str]] = set()
    skipped_404 = 0
    fetched_ok = 0

    for index, company in enumerate(companies):
        if index and delay > 0:
            time.sleep(delay)
        try:
            jobs = fetcher.fetch(company)
        except BoardNotFoundError as exc:
            skipped_404 += 1
            logger.warning(
                "Skipping %s (%s/%s): %s",
                company.name,
                company.ats,
                company.slug,
                exc,
            )
            continue
        except ATSClientError as exc:
            failed_keys.add((company.ats, company.slug))
            logger.warning("Fetch error for %s: %s", company.name, exc)
            continue

        fetched_ok += 1
        for job in jobs:
            if job_matches(job, config.title_patterns, config.locations):
                matched[job.id] = job

    current = merge_current_with_previous(previous, matched, failed_keys)
    diff = diff_snapshots(previous, current)
    save_snapshot(snapshot_path, current)
    markdown = render_report(
        diff,
        companies_fetched=fetched_ok,
        boards_skipped=skipped_404,
    )
    write_report(report_path, markdown)
    logger.info("%s", stdout_summary(diff, report_path))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Poll Greenhouse, Lever, and Ashby boards for mobile EM / director roles."
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to jobs.yaml (default: config/jobs.yaml, then jobs.local.yaml)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Probe configured slugs and skip 404s; do not write a snapshot",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for snapshot.json and report.md (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Seconds to wait between company requests (default: from config)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    config_path = args.config if args.config is not None else DEFAULT_JOBS_YAML
    resolved = resolve_config_path(config_path)
    if not resolved.exists():
        logger.error("Config file not found: %s", resolved)
        raise SystemExit(1)

    config = load_jobs_config(resolved)
    output_dir = args.output_dir
    snapshot_path = output_dir / "snapshot.json"
    report_path = output_dir / "report.md"
    fetcher = LiveFetcher(make_session(), config.sources)
    code = run(
        config,
        fetcher,
        snapshot_path,
        report_path,
        validate_only=args.validate_only,
        delay_seconds=args.delay,
    )
    raise SystemExit(code)


if __name__ == "__main__":
    main()
