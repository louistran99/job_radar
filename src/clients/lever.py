"""Lever postings API (public, no auth)."""

from __future__ import annotations

from typing import Any

from src.models import Company, Job
from src.locations import dedupe_locations, split_location_text

SOURCE = "lever"


def extract_jobs(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [job for job in payload if isinstance(job, dict)]
    if isinstance(payload, dict):
        jobs = payload.get("data") or payload.get("postings") or []
        return [job for job in jobs if isinstance(job, dict)]
    return []


def normalize(raw: dict[str, Any], company: Company) -> Job | None:
    job_id = raw.get("id")
    if job_id is None:
        return None
    title = str(raw.get("text") or raw.get("title") or "").strip()
    if not title:
        return None

    categories = raw.get("categories") or {}
    if not isinstance(categories, dict):
        categories = {}

    locations: list[str] = []
    locations.extend(split_location_text(str(categories.get("location") or "")))
    all_locations = categories.get("allLocations") or []
    if isinstance(all_locations, list):
        for loc in all_locations:
            locations.extend(split_location_text(str(loc or "")))

    locations = dedupe_locations(locations)
    workplace = raw.get("workplaceType")
    workplace_type = str(workplace).strip() if workplace else None
    is_remote = (workplace_type or "").lower().replace("-", "").replace(
        " ", ""
    ) == "remote" or any("remote" in loc.lower() for loc in locations)
    url = str(raw.get("hostedUrl") or raw.get("applyUrl") or "")
    return Job(
        ats=SOURCE,
        slug=company.slug,
        job_id=str(job_id),
        company=company.name,
        title=title,
        url=url,
        locations=locations,
        is_remote=is_remote,
        workplace_type=workplace_type,
    )
