"""Fetch and normalize jobs for one company board."""

from __future__ import annotations

from typing import Protocol

from src.clients.http import ATSClientError, BoardNotFoundError, get_json
from src.models import Company, Job
from src.normalize import jobs_from_payload


class Fetcher(Protocol):
    def fetch(self, company: Company) -> list[Job]:
        """Return normalized jobs or raise BoardNotFoundError / ATSClientError."""


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
        payload = get_json(self.session, url)
        return jobs_from_payload(company.ats, payload, company)
