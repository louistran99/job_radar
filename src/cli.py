"""Fetch, match, and report ATS jobs."""

from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Callable
from pathlib import Path

from src.bootstrap import REPO_ROOT, progress, status
from src.clients.http import ATSClientError, BoardNotFoundError, make_session
from src.config import (
    DEFAULT_JOBS_JSON,
    JobsConfig,
    enabled_companies,
    load_app_config,
    resolve_companies_path,
    resolve_jobs_path,
)
from src.fetch import Fetcher, LiveFetcher
from src.match import job_matches
from src.models import Company, Job
from src.report import render_report, stdout_summary, write_report
from src.snapshot import (
    diff_snapshots,
    load_snapshot,
    merge_current_with_previous,
    save_snapshot,
)
from src.validate import validate_companies

DEFAULT_OUTPUT_DIR = REPO_ROOT / "output"
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
    replace_report: bool = False,
    on_progress: Callable[[int, str], None] | None = None,
) -> int:
    companies = enabled_companies(config)
    if not companies:
        logger.error(
            "No enabled companies to fetch. Check config/companies.json and config/ats.json."
        )
        return 1

    delay = config.delay_seconds if delay_seconds is None else delay_seconds
    total = len(companies)

    if validate_only:
        if on_progress:
            on_progress(4, "Probe configured slugs")

        def _probe_progress(company: Company, index: int, count: int) -> None:
            if on_progress:
                status(f"probe {company.name} — {index}/{count}")

        valid, skipped = validate_companies(
            fetcher,
            companies,
            on_company=_probe_progress if on_progress else None,
        )
        for company in valid:
            logger.info("OK %s (%s/%s)", company.name, company.ats, company.slug)
        logger.info("Valid: %s  Skipped: %s", len(valid), len(skipped))
        if on_progress:
            on_progress(5, "Validation complete — no snapshot")
        return 0

    if on_progress:
        on_progress(4, "Fetch and match jobs")

    previous = load_snapshot(snapshot_path)
    matched: dict[str, Job] = {}
    failed_keys: set[tuple[str, str]] = set()
    skipped_404 = 0
    fetched_ok = 0
    total_fetched = 0

    for index, company in enumerate(companies):
        if on_progress:
            status(f"fetch {company.name} — {index + 1}/{total}")
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
        total_fetched += len(jobs)
        company_matched: list[Job] = []
        for job in jobs:
            if job_matches(
                job,
                config.level_patterns,
                config.domain_patterns,
                config.locations,
            ):
                matched[job.id] = job
                company_matched.append(job)
        logger.debug(
            "%s: %s job(s) fetched, %s matched",
            company.name,
            len(jobs),
            len(company_matched),
        )
        for job in company_matched:
            loc = ", ".join(job.locations) or "(no location)"
            logger.debug("  matched: %s — %s [%s]", job.company, job.title, loc)

    logger.debug(
        "Fetched %s job(s) from %s board(s); %s matched filters",
        total_fetched,
        fetched_ok,
        len(matched),
    )

    if on_progress:
        on_progress(5, "Write snapshot and report")
    current = merge_current_with_previous(previous, matched, failed_keys)
    diff = diff_snapshots(previous, current)
    save_snapshot(snapshot_path, current)
    markdown = render_report(
        diff,
        companies_fetched=fetched_ok,
        boards_skipped=skipped_404,
    )
    prepended = report_path.exists() and not replace_report
    write_report(report_path, markdown, replace=replace_report)
    logger.info("%s", stdout_summary(diff, report_path, prepended=prepended))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Poll Greenhouse, Lever, Ashby, and Gem boards for mobile EM / director roles."
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to jobs.json (default: config/jobs.json, then jobs.local.json)",
    )
    parser.add_argument(
        "--small-set",
        type=Path,
        dest="small_set",
        help="Path to a companies JSON subset (default: config/companies.json). "
        "Relative names also resolve under config/, e.g. --small-set smallset.json",
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
        "--replace-report",
        action="store_true",
        help="Overwrite output/report.md instead of prepending this run",
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
    if args.verbose:
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    progress(3, "Load config")
    config_path = args.config if args.config is not None else DEFAULT_JOBS_JSON
    resolved = resolve_jobs_path(config_path)
    if not resolved.exists():
        logger.error("Config file not found: %s", resolved)
        raise SystemExit(1)

    companies_path = resolve_companies_path(args.small_set)
    config = load_app_config(resolved, companies_path=companies_path)
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
        replace_report=args.replace_report,
        on_progress=progress,
    )
    raise SystemExit(code)
