from __future__ import annotations

from src.clients.http import ATSClientError, BoardNotFoundError
from src.models import Company, Job


class FakeFetcher:
    """In-memory ATS fetcher for unit tests. Does not call the network."""

    def __init__(
        self,
        jobs: dict[tuple[str, str], list[Job]] | None = None,
        missing: set[tuple[str, str]] | None = None,
        errors: dict[tuple[str, str], str] | None = None,
    ) -> None:
        self.jobs = jobs or {}
        self.missing = missing or set()
        self.errors = errors or {}
        self.calls: list[Company] = []

    def fetch(self, company: Company) -> list[Job]:
        self.calls.append(company)
        key = (company.ats, company.slug)
        if key in self.missing:
            raise BoardNotFoundError(
                f"Board not found: {company.ats}/{company.slug} (404)"
            )
        if key in self.errors:
            raise ATSClientError(self.errors[key])
        return list(self.jobs.get(key, []))
