"""Greenhouse Job Board API (public, no auth)."""

from __future__ import annotations

from typing import Any

from src.models import Company, Job
from src.locations import dedupe_locations, split_location_text

SOURCE = "greenhouse"


def extract_jobs(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        jobs = payload.get("jobs") or []
        return [job for job in jobs if isinstance(job, dict)]
    return []


def normalize(raw: dict[str, Any], company: Company) -> Job | None:
    job_id = raw.get("id")
    if job_id is None:
        return None
    title = str(raw.get("title") or "").strip()
    if not title:
        return None

    locations: list[str] = []
    loc = raw.get("location")
    if isinstance(loc, dict):
        locations.extend(split_location_text(str(loc.get("name") or "")))
    elif isinstance(loc, str):
        locations.extend(split_location_text(loc))

    for office in raw.get("offices") or []:
        if not isinstance(office, dict):
            continue
        locations.extend(split_location_text(str(office.get("name") or "")))
        office_loc = office.get("location")
        if isinstance(office_loc, str):
            locations.extend(split_location_text(office_loc))
        elif isinstance(office_loc, dict):
            locations.extend(
                split_location_text(str(office_loc.get("name") or ""))
            )

    locations = dedupe_locations(locations)
    is_remote = any("remote" in loc.lower() for loc in locations)
    url = str(raw.get("absolute_url") or "")
    return Job(
        ats=SOURCE,
        slug=company.slug,
        job_id=str(job_id),
        company=company.name,
        title=title,
        url=url,
        locations=locations,
        is_remote=is_remote,
        workplace_type=None,
    )
