"""BambooHR careers list (public, no auth).

GET https://{slug}.bamboohr.com/careers/list
Returns every open job in one response; there is no pagination. Openings carry
no URL, so it is built from the slug and opening id.

`locationType` is BambooHR's workplace flag. Remote openings put their region in
`atsLocation` and leave `location` null; onsite and hybrid openings do the
reverse.
"""

from __future__ import annotations

from typing import Any

from src.models import Company, Job
from src.locations import (
    dedupe_locations,
    join_location_parts,
    split_location_text,
)

SOURCE = "bamboohr"

JOB_URL = "https://{slug}.bamboohr.com/careers/{job_id}"

_WORKPLACE_TYPES = {"0": "onsite", "1": "remote", "2": "hybrid"}


def extract_jobs(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    result = payload.get("result") or []
    return [job for job in result if isinstance(job, dict)]


def _workplace_type(location_type: Any) -> str | None:
    if location_type is None:
        return None
    return _WORKPLACE_TYPES.get(str(location_type).strip())


def _locations(raw: dict[str, Any]) -> list[str]:
    candidates: list[str] = []

    ats_location = raw.get("atsLocation")
    if isinstance(ats_location, dict):
        candidates.append(
            join_location_parts(
                [
                    str(ats_location.get("city") or ""),
                    str(ats_location.get("state") or ""),
                    str(ats_location.get("province") or ""),
                    str(ats_location.get("country") or ""),
                ]
            )
        )

    location = raw.get("location")
    if isinstance(location, dict):
        candidates.append(
            join_location_parts(
                [
                    str(location.get("city") or ""),
                    str(location.get("state") or ""),
                    str(location.get("addressCountry") or ""),
                ]
            )
        )

    locations: list[str] = []
    for candidate in candidates:
        locations.extend(split_location_text(candidate))
    return dedupe_locations(locations)


def normalize(raw: dict[str, Any], company: Company) -> Job | None:
    job_id = raw.get("id")
    if job_id is None:
        return None
    title = str(raw.get("jobOpeningName") or "").strip()
    if not title:
        return None

    locations = _locations(raw)
    workplace_type = _workplace_type(raw.get("locationType"))
    is_remote = (
        workplace_type == "remote"
        or bool(raw.get("isRemote"))
        or any("remote" in loc.lower() for loc in locations)
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
