"""Gem Job Board API (public, no auth).

GET https://api.gem.com/job_board/v0/{slug}/job_posts/
"""

from __future__ import annotations

from typing import Any

from src.models import Company, Job
from src.locations import dedupe_locations, split_location_text

SOURCE = "gem"

_ONSITE_TYPES = frozenset({"in_office", "on_site", "onsite"})


def extract_jobs(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [job for job in payload if isinstance(job, dict)]
    return []


def _workplace_type(location_type: Any) -> str | None:
    if location_type is None:
        return None
    raw = str(location_type).strip()
    if not raw:
        return None
    key = raw.casefold().replace("-", "_").replace(" ", "_")
    if key in _ONSITE_TYPES:
        return "onsite"
    return raw


def _office_location_text(office: dict[str, Any]) -> str:
    office_loc = office.get("location")
    if isinstance(office_loc, dict):
        name = str(office_loc.get("name") or "").strip()
        if name:
            return name
    elif isinstance(office_loc, str) and office_loc.strip():
        return office_loc.strip()
    return str(office.get("name") or "").strip()


def _locations(raw: dict[str, Any]) -> list[str]:
    locations: list[str] = []
    offices = raw.get("offices") or []
    if isinstance(offices, list):
        for office in offices:
            if not isinstance(office, dict):
                continue
            locations.extend(split_location_text(_office_location_text(office)))

    if not locations:
        loc = raw.get("location")
        if isinstance(loc, dict):
            locations.extend(split_location_text(str(loc.get("name") or "")))
        elif isinstance(loc, str):
            locations.extend(split_location_text(loc))

    return dedupe_locations(locations)


def normalize(raw: dict[str, Any], company: Company) -> Job | None:
    job_id = raw.get("id")
    if job_id is None:
        return None
    title = str(raw.get("title") or "").strip()
    if not title:
        return None

    locations = _locations(raw)
    workplace_type = _workplace_type(raw.get("location_type"))
    is_remote = (workplace_type or "").casefold() == "remote" or any(
        "remote" in loc.lower() for loc in locations
    )
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
        workplace_type=workplace_type,
    )
