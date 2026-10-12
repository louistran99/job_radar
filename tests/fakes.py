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


class FakeStore:
    """In-memory stand-in for the Supabase tables. Does not call the network."""

    def __init__(self, lose: set[str] | None = None) -> None:
        self.lose = lose or set()  # external_ids that never reach the table
        self.companies: dict[tuple[str, str], str] = {}
        self.jobs: dict[tuple[str, str], dict] = {}

    def upsert_companies(self, companies: list[Company]) -> dict[tuple[str, str], str]:
        for company in companies:
            key = (company.ats, company.slug)
            self.companies.setdefault(key, f"id-{company.ats}-{company.slug}")
        return dict(self.companies)

    def upsert_jobs(self, rows: list[dict]) -> None:
        keys = [(row["company_id"], row["external_id"]) for row in rows]
        # Postgres rejects an upsert that touches the same row twice.
        assert len(keys) == len(set(keys)), "duplicate row in one upsert"
        for key, row in zip(keys, rows):
            if row["external_id"] not in self.lose:
                self.jobs[key] = row

    def external_ids_for(self, company_id: str) -> set[str]:
        return {ext for cid, ext in self.jobs if cid == company_id}
