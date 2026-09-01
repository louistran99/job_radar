"""Probe company slugs; 404s are skipped rather than hard failures."""

from __future__ import annotations

import logging
from typing import Any

from src.clients.http import ATSClientError, BoardNotFoundError
from src.fetch import Fetcher
from src.models import Company, Job

logger = logging.getLogger(__name__)


def probe_company(fetcher: Fetcher, company: Company) -> tuple[list[Job] | None, str | None]:
    """Return (jobs, None) on success, (None, reason) on skip/error.

    Board 404s are skips, not fatal.
    """
    try:
        return fetcher.fetch(company), None
    except BoardNotFoundError as exc:
        return None, str(exc)
    except ATSClientError as exc:
        return None, str(exc)


def validate_companies(
    fetcher: Fetcher, companies: list[Company]
) -> tuple[list[Company], list[tuple[Company, str]]]:
    valid: list[Company] = []
    skipped: list[tuple[Company, str]] = []
    for company in companies:
        jobs, error = probe_company(fetcher, company)
        if error is None:
            valid.append(company)
            continue
        skipped.append((company, error))
        logger.warning(
            "Skipping %s (%s/%s): %s",
            company.name,
            company.ats,
            company.slug,
            error,
        )
    return valid, skipped


def exit_code(*, companies: list[Any], fatal: bool = False) -> int:
    if fatal or not companies:
        return 1
    return 0
