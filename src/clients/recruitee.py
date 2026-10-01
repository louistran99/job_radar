"""Recruitee careers API (public, no auth).

GET https://{slug}.recruitee.com/api/offers/
Returns every offer in one response; there is no pagination.
"""

from __future__ import annotations

from typing import Any

from src.models import Company, Job
from src.locations import (
    dedupe_locations,
    join_location_parts,
    split_location_text,
)

SOURCE = "recruitee"


def extract_jobs(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    offers = payload.get("offers") or []
    published: list[dict[str, Any]] = []
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        status = offer.get("status")
        if status is not None and str(status) != "published":
            continue
        published.append(offer)
    return published


def _locations(raw: dict[str, Any]) -> list[str]:
    locations: list[str] = []
    entries = raw.get("locations")
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            text = join_location_parts(
                [
                    str(entry.get("city") or entry.get("name") or ""),
                    str(entry.get("state") or ""),
                    str(entry.get("country") or ""),
                ]
            )
            locations.extend(split_location_text(text))

    if not locations:
        locations.extend(split_location_text(str(raw.get("location") or "")))

    if not locations:
        text = join_location_parts(
            [
                str(raw.get("city") or ""),
                str(raw.get("state_name") or ""),
                str(raw.get("country") or ""),
            ]
        )
        locations.extend(split_location_text(text))

    return dedupe_locations(locations)


def _workplace_type(raw: dict[str, Any]) -> str | None:
    if raw.get("remote"):
        return "remote"
    if raw.get("hybrid"):
        return "hybrid"
    if raw.get("on_site"):
        return "onsite"
    return None


def normalize(raw: dict[str, Any], company: Company) -> Job | None:
    job_id = raw.get("id")
    if job_id is None:
        return None
    title = str(raw.get("title") or "").strip()
    if not title:
        return None

    locations = _locations(raw)
    workplace_type = _workplace_type(raw)
    is_remote = workplace_type == "remote" or any(
        "remote" in loc.lower() for loc in locations
    )
    url = str(raw.get("careers_url") or raw.get("careers_apply_url") or "")
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
