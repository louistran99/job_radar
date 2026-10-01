"""Fetch and normalize jobs for one company board."""

from __future__ import annotations

import logging
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from src.clients.http import ATSClientError, BoardNotFoundError, get_json
from src.models import Company, Job
from src.normalize import extract_raw, jobs_from_payload, normalize_raw

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 20


class Fetcher(Protocol):
    def fetch(self, company: Company) -> list[Job]:
        """Return normalized jobs or raise BoardNotFoundError / ATSClientError."""


def _with_params(url: str, params: dict[str, Any]) -> str:
    parts = urlparse(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query.extend((key, str(value)) for key, value in params.items())
    return urlunparse(parts._replace(query=urlencode(query)))


class LiveFetcher:
    def __init__(self, session, sources: dict[str, dict]) -> None:
        self.session = session
        self.sources = sources

    def fetch(self, company: Company) -> list[Job]:
        source = self.sources.get(company.ats) or {}
        template = source.get("url")
        if not template:
            raise ATSClientError(f"No URL template for ATS {company.ats}")
        try:
            url = str(template).format(slug=company.slug)
        except (KeyError, IndexError, ValueError) as exc:
            raise ATSClientError(
                f"Bad URL template for {company.ats}: {template}"
            ) from exc
        page = source.get("page")
        if isinstance(page, dict):
            return self._fetch_pages(company, url, page)
        payload = get_json(self.session, url)
        return jobs_from_payload(company.ats, payload, company)

    def _fetch_pages(
        self, company: Company, url: str, page: dict[str, Any]
    ) -> list[Job]:
        """Walk offset pages until a short page arrives or max_pages is hit."""
        size = max(1, int(page.get("size") or DEFAULT_PAGE_SIZE))
        max_pages = max(1, int(page.get("max_pages") or DEFAULT_MAX_PAGES))
        limit_param = str(page.get("limit_param") or "limit")
        offset_param = str(page.get("offset_param") or "offset")

        raw_jobs: list[dict[str, Any]] = []
        for index in range(max_pages):
            paged_url = _with_params(
                url, {limit_param: size, offset_param: index * size}
            )
            batch = extract_raw(company.ats, get_json(self.session, paged_url))
            raw_jobs.extend(batch)
            if len(batch) < size:
                break
        else:
            logger.warning(
                "%s (%s): stopped after %s page(s) of %s; board may have more jobs",
                company.name,
                company.ats,
                max_pages,
                size,
            )

        return normalize_raw(company.ats, raw_jobs, company)
