"""Ashby public job board API (no auth)."""

from __future__ import annotations

from typing import Any

from src.models import Company, Job
from src.locations import dedupe_locations, split_location_text

SOURCE = "ashby"


def extract_jobs(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    jobs = payload.get("jobs") or []
    listed: list[dict[str, Any]] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        if job.get("isListed") is False:
            continue
        listed.append(job)
    return listed


def normalize(raw: dict[str, Any], company: Company) -> Job | None:
    job_id = raw.get("id")
    if job_id is None:
        return None
    title = str(raw.get("title") or "").strip()
    if not title:
        return None

    locations: list[str] = []
    locations.extend(split_location_text(str(raw.get("location") or "")))
    location_name = raw.get("locationName")
    if location_name:
        locations.extend(split_location_text(str(location_name)))

    for secondary in raw.get("secondaryLocations") or []:
        if isinstance(secondary, dict):
            locations.extend(
                split_location_text(str(secondary.get("location") or ""))
            )
        elif isinstance(secondary, str):
            locations.extend(split_location_text(secondary))

    locations = dedupe_locations(locations)
    workplace = raw.get("workplaceType")
    workplace_type = str(workplace).strip() if workplace else None
    is_remote = bool(raw.get("isRemote"))
    url = str(raw.get("jobUrl") or raw.get("applyUrl") or "")
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
