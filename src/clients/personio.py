"""Personio job board search feed (public, no auth).

GET https://{slug}.jobs.personio.de/search.json
Returns a bare array of every published position; there is no pagination.
Positions carry no URL, so it is built from the slug and position id.
"""

from __future__ import annotations

from typing import Any

from src.models import Company, Job
from src.locations import dedupe_locations, split_location_text

SOURCE = "personio"

JOB_URL = "https://{slug}.jobs.personio.de/job/{job_id}"


def extract_jobs(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [job for job in payload if isinstance(job, dict)]
    return []


def _locations(raw: dict[str, Any]) -> list[str]:
    locations: list[str] = []
    offices = raw.get("offices")
    if isinstance(offices, list):
        for office in offices:
            locations.extend(split_location_text(str(office or "")))

    if not locations:
        # `office` joins several office names with commas, e.g. "Berlin,Munich".
        for office in str(raw.get("office") or "").split(","):
            locations.extend(split_location_text(office))

    return dedupe_locations(locations)


def normalize(raw: dict[str, Any], company: Company) -> Job | None:
    job_id = raw.get("id")
    if job_id is None:
        return None
    title = str(raw.get("name") or "").strip()
    if not title:
        return None

    locations = _locations(raw)
    is_remote = any("remote" in loc.lower() for loc in locations)
    return Job(
        ats=SOURCE,
        slug=company.slug,
        job_id=str(job_id),
        company=company.name,
        title=title,
        url=JOB_URL.format(slug=company.slug, job_id=job_id),
        locations=locations,
        is_remote=is_remote,
        workplace_type="remote" if is_remote else None,
    )
