"""Workable job board widget API (public, no auth).

GET https://apply.workable.com/api/v1/widget/accounts/{slug}
Returns every published job in one response; there is no pagination.
"""

from __future__ import annotations

from typing import Any

from src.models import Company, Job
from src.locations import (
    dedupe_locations,
    join_location_parts,
    split_location_text,
)
from src.timestamps import parse_timestamp

SOURCE = "workable"


def extract_jobs(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    jobs = payload.get("jobs") or []
    return [job for job in jobs if isinstance(job, dict)]


def _locations(raw: dict[str, Any]) -> list[str]:
    locations: list[str] = []
    entries = raw.get("locations")
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            text = join_location_parts(
                [
                    str(entry.get("city") or ""),
                    str(entry.get("region") or ""),
                    str(entry.get("country") or ""),
                ]
            )
            locations.extend(split_location_text(text))

    if not locations:
        text = join_location_parts(
            [
                str(raw.get("city") or ""),
                str(raw.get("state") or ""),
                str(raw.get("country") or ""),
            ]
        )
        locations.extend(split_location_text(text))

    return dedupe_locations(locations)


def normalize(raw: dict[str, Any], company: Company) -> Job | None:
    job_id = raw.get("shortcode")
    if not job_id:
        return None
    title = str(raw.get("title") or "").strip()
    if not title:
        return None

    locations = _locations(raw)
    is_remote = bool(raw.get("telecommuting")) or any(
        "remote" in loc.lower() for loc in locations
    )
    url = str(
        raw.get("url") or raw.get("shortlink") or raw.get("application_url") or ""
    )
    return Job(
        ats=SOURCE,
        slug=company.slug,
        job_id=str(job_id),
        company=company.name,
        title=title,
        url=url,
        locations=locations,
        is_remote=is_remote,
        workplace_type="remote" if raw.get("telecommuting") else None,
        # published_on is a date, so it lands at midnight UTC.
        posted_at=parse_timestamp(raw.get("published_on")),
    )
