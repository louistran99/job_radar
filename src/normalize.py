"""Turn ATS-specific payloads into Job records."""

from __future__ import annotations

from typing import Any, Callable

from src.clients import (
    ashby,
    bamboohr,
    gem,
    greenhouse,
    lever,
    personio,
    recruitee,
    smartrecruiters,
    workable,
)
from src.models import Company, Job

_EXTRACTORS: dict[str, Callable[[Any], list[dict[str, Any]]]] = {
    "greenhouse": greenhouse.extract_jobs,
    "lever": lever.extract_jobs,
    "ashby": ashby.extract_jobs,
    "gem": gem.extract_jobs,
    "smartrecruiters": smartrecruiters.extract_jobs,
    "workable": workable.extract_jobs,
    "recruitee": recruitee.extract_jobs,
    "personio": personio.extract_jobs,
    "bamboohr": bamboohr.extract_jobs,
}

_NORMALIZERS: dict[str, Callable[[dict[str, Any], Company], Job | None]] = {
    "greenhouse": greenhouse.normalize,
    "lever": lever.normalize,
    "ashby": ashby.normalize,
    "gem": gem.normalize,
    "smartrecruiters": smartrecruiters.normalize,
    "workable": workable.normalize,
    "recruitee": recruitee.normalize,
    "personio": personio.normalize,
    "bamboohr": bamboohr.normalize,
}


def extract_raw(ats: str, payload: Any) -> list[dict[str, Any]]:
    """Pull the raw posting records out of an ATS payload."""
    extractor = _EXTRACTORS.get(ats)
    if extractor is None:
        raise ValueError(f"Unsupported ATS: {ats}")
    return extractor(payload)


def normalize_raw(
    ats: str, raw_jobs: list[dict[str, Any]], company: Company
) -> list[Job]:
    normalizer = _NORMALIZERS.get(ats)
    if normalizer is None:
        raise ValueError(f"Unsupported ATS: {ats}")
    jobs: list[Job] = []
    for raw in raw_jobs:
        job = normalizer(raw, company)
        if job is not None:
            jobs.append(job)
    return jobs


def jobs_from_payload(ats: str, payload: Any, company: Company) -> list[Job]:
    return normalize_raw(ats, extract_raw(ats, payload), company)
