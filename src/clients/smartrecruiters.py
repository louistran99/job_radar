"""SmartRecruiters Posting API (public, no auth).

GET https://api.smartrecruiters.com/v1/companies/{slug}/postings
Paged with ?limit=&offset=; the API caps limit at 100 regardless of what we ask.
Postings carry no public job URL, so it is built from the slug and posting id.
"""

from __future__ import annotations

from typing import Any

from src.models import Company, Job
from src.locations import (
    dedupe_locations,
    join_location_parts,
    split_location_text,
)

SOURCE = "smartrecruiters"

JOB_URL = "https://jobs.smartrecruiters.com/{slug}/{job_id}"


def extract_jobs(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    content = payload.get("content") or []
    return [job for job in content if isinstance(job, dict)]


def _clean_full_location(text: str) -> str:
    """Drop the empty segments SmartRecruiters leaves in "city, , Country"."""
    parts = [part.strip() for part in text.split(",")]
    return ", ".join(part for part in parts if part)


def _locations(location: dict[str, Any]) -> list[str]:
    full = _clean_full_location(str(location.get("fullLocation") or ""))
    if full:
        return dedupe_locations(split_location_text(full))

    joined = join_location_parts(
        [str(location.get(key) or "") for key in ("city", "region", "country")]
    )
    return dedupe_locations(split_location_text(joined))


def _workplace_type(location: dict[str, Any]) -> str | None:
    if location.get("remote"):
        return "remote"
    if location.get("hybrid"):
        return "hybrid"
    return None


def normalize(raw: dict[str, Any], company: Company) -> Job | None:
    job_id = raw.get("id")
    if job_id is None:
        return None
    title = str(raw.get("name") or "").strip()
    if not title:
        return None

    location = raw.get("location")
    if not isinstance(location, dict):
        location = {}

    locations = _locations(location)
    workplace_type = _workplace_type(location)
    is_remote = workplace_type == "remote" or any(
        "remote" in loc.lower() for loc in locations
    )
    return Job(
        ats=SOURCE,
        slug=company.slug,
        job_id=str(job_id),
        company=company.name,
        title=title,
        url=JOB_URL.format(slug=company.slug, job_id=job_id),
        locations=locations,
        is_remote=is_remote,
        workplace_type=workplace_type,
    )
