"""Fetch every company's jobs and export them to the Supabase `jobs` table."""

from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from src.bootstrap import REPO_ROOT, progress
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
from src.models import Company, Job
from src.supabase_export import ExportError, SupabaseStore, load_settings

LOG_FILE = REPO_ROOT / "output" / "fetchjobs.log"
WORKPLACE_TYPES = frozenset({"remote", "hybrid", "onsite"})

logger = logging.getLogger(__name__)


class JobStore(Protocol):
    def upsert_companies(
        self, companies: list[Company]
    ) -> dict[tuple[str, str], str]: ...

    def upsert_jobs(self, rows: list[dict[str, Any]]) -> None: ...

    def external_ids_for(self, company_id: str) -> set[str]: ...


@dataclass
class FetchedBoard:
    company: Company
    jobs: list[Job]


@dataclass
class ExportResult:
    exported: dict[str, int] = field(default_factory=dict)  # company -> jobs written
    empty: list[str] = field(default_factory=list)  # fetched, no jobs
    skipped: list[str] = field(default_factory=list)  # fetch failed or 404
    missing: dict[str, int] = field(default_factory=dict)  # company -> rows not read back

    @property
    def ok(self) -> bool:
        return not self.missing


def job_row(job: Job, company_id: str) -> dict[str, Any]:
    """Map a Job onto a `jobs` table row. Job has no salary, so salary_text is omitted."""
    return {
        "company_id": company_id,
        "external_id": job.job_id,
        "title": job.title,
        "url": job.url,
        "locations": job.locations,
        "workplace_type": (
            job.workplace_type if job.workplace_type in WORKPLACE_TYPES else None
        ),
        "posted_at": job.posted_at.isoformat() if job.posted_at else None,
    }


def build_rows(board: FetchedBoard, company_id: str) -> list[dict[str, Any]]:
    """Map a board's jobs to rows, keeping the last job when a job_id repeats.

    One upsert statement cannot touch the same (company_id, external_id) twice.
    """
    rows: dict[str, dict[str, Any]] = {}
    for job in board.jobs:
        if job.job_id in rows:
            logger.warning(
                "%s returned job_id %s more than once; keeping the last one",
                board.company.name,
                job.job_id,
            )
        rows[job.job_id] = job_row(job, company_id)
        logger.info(
            "Mapped %s job %s to a jobs row: %s", board.company.name, job.job_id, job.title
        )
    return list(rows.values())


def fetch_boards(
    companies: list[Company], fetcher: Fetcher, delay_seconds: float
) -> tuple[list[FetchedBoard], list[str]]:
    """Fetch each company once. Returns the boards fetched and the names skipped."""
    boards: list[FetchedBoard] = []
    skipped: list[str] = []
    seen: set[tuple[str, str]] = set()
    for index, company in enumerate(companies):
        key = (company.ats, company.slug)
        if key in seen:
            logger.warning(
                "Skipping %s: %s/%s is already listed", company.name, company.ats, company.slug
            )
            continue
        seen.add(key)
        if index and delay_seconds > 0:
            time.sleep(delay_seconds)
        logger.info("Fetching jobs for %s (%s/%s)", company.name, company.ats, company.slug)
        try:
            jobs = fetcher.fetch(company)
        except BoardNotFoundError as exc:
            logger.warning("Skipping %s: %s", company.name, exc)
            skipped.append(company.name)
            continue
        except ATSClientError as exc:
            logger.warning("Fetch error for %s: %s", company.name, exc)
            skipped.append(company.name)
            continue
        logger.info("Fetched %s job(s) for %s", len(jobs), company.name)
        boards.append(FetchedBoard(company, jobs))
    return boards, skipped


def run_export(
    config: JobsConfig,
    fetcher: Fetcher,
    store: JobStore,
    *,
    delay_seconds: float | None = None,
    on_progress: Callable[[int, str], None] | None = None,
) -> ExportResult:
    companies = enabled_companies(config)
    if not companies:
        raise ExportError(
            "No enabled companies to fetch. Check the companies file and config/ats.json."
        )
    delay = config.delay_seconds if delay_seconds is None else delay_seconds

    if on_progress:
        on_progress(4, "Fetch jobs")
    boards, skipped = fetch_boards(companies, fetcher, delay)
    result = ExportResult(skipped=skipped)

    if on_progress:
        on_progress(5, "Export to Supabase and verify")
    company_ids = store.upsert_companies([board.company for board in boards])
    logger.info("Upserted %s compan(ies) to Supabase", len(company_ids))

    expected_ids: dict[str, tuple[str, set[str]]] = {}  # company_id -> (name, ids)
    for board in boards:
        name = board.company.name
        if not board.jobs:
            logger.info("%s returned no jobs; nothing to export", name)
            result.empty.append(name)
            continue
        company_id = company_ids[(board.company.ats, board.company.slug)]
        rows = build_rows(board, company_id)
        store.upsert_jobs(rows)
        logger.info("Exported %s job(s) for %s to the jobs table", len(rows), name)
        result.exported[name] = len(rows)
        expected_ids[company_id] = (name, {row["external_id"] for row in rows})

    for company_id, (name, expected) in expected_ids.items():
        missing = expected - store.external_ids_for(company_id)
        if missing:
            logger.error("Verify failed for %s: %s row(s) not in Supabase", name, len(missing))
            result.missing[name] = len(missing)
        else:
            logger.info("Verified %s: all %s row(s) are in Supabase", name, len(expected))
    return result


def summary(result: ExportResult) -> str:
    lines = [
        f"Exported {sum(result.exported.values())} job(s) "
        f"from {len(result.exported)} company(ies)."
    ]
    if result.empty:
        lines.append(f"No jobs returned: {', '.join(result.empty)}")
    if result.skipped:
        lines.append(f"Skipped (404 or fetch error): {', '.join(result.skipped)}")
    if result.missing:
        for name, count in result.missing.items():
            lines.append(f"VERIFY FAILED: {name} is missing {count} row(s) in Supabase")
    else:
        lines.append("Verified: every exported row was read back from Supabase.")
    return "\n".join(lines)


def configure_logging(enable_logging: bool, log_path: Path = LOG_FILE) -> None:
    """Warnings go to the console. With enable_logging, every step also goes to log_path."""
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    handlers: list[logging.Handler] = [console]
    if enable_logging:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        handlers.append(file_handler)
    logging.basicConfig(
        level=logging.INFO if enable_logging else logging.WARNING,
        handlers=handlers,
        force=True,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Fetch jobs for every company in a file and export them to Supabase."
    )
    parser.add_argument(
        "--companies",
        type=Path,
        help="Path to a companies JSON file (default: config/companies.json). "
        "Relative names also resolve under config/, e.g. --companies smallset.json",
    )
    parser.add_argument(
        "--enable-logging",
        action="store_true",
        help=f"Write each step to {LOG_FILE}",
    )
    args = parser.parse_args(argv)
    configure_logging(args.enable_logging)

    progress(3, "Load config")
    try:
        settings = load_settings()
    except ExportError as exc:
        raise SystemExit(str(exc)) from None
    config = load_app_config(
        resolve_jobs_path(DEFAULT_JOBS_JSON),
        companies_path=resolve_companies_path(args.companies),
    )
    session = make_session()
    try:
        result = run_export(
            config,
            LiveFetcher(session, config.sources),
            SupabaseStore(session, settings),
            on_progress=progress,
        )
    except ExportError as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from None

    print(summary(result), flush=True)
    if args.enable_logging:
        print(f"Log written to {LOG_FILE}", flush=True)
    raise SystemExit(0 if result.ok else 1)
