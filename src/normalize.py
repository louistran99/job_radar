"""Turn ATS-specific payloads into Job records."""

from __future__ import annotations

from typing import Any, Callable

from src.clients import ashby, gem, greenhouse, lever
from src.models import Company, Job

_EXTRACTORS: dict[str, Callable[[Any], list[dict[str, Any]]]] = {
    "greenhouse": greenhouse.extract_jobs,
    "lever": lever.extract_jobs,
    "ashby": ashby.extract_jobs,
    "gem": gem.extract_jobs,
}

_NORMALIZERS: dict[str, Callable[[dict[str, Any], Company], Job | None]] = {
    "greenhouse": greenhouse.normalize,
    "lever": lever.normalize,
    "ashby": ashby.normalize,
    "gem": gem.normalize,
}


def jobs_from_payload(ats: str, payload: Any, company: Company) -> list[Job]:
    extractor = _EXTRACTORS.get(ats)
    normalizer = _NORMALIZERS.get(ats)
    if extractor is None or normalizer is None:
        raise ValueError(f"Unsupported ATS: {ats}")
    jobs: list[Job] = []
    for raw in extractor(payload):
        job = normalizer(raw, company)
        if job is not None:
            jobs.append(job)
    return jobs
