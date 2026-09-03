"""Title and location matching."""

from __future__ import annotations

import re

from src.models import Job

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_SR = re.compile(r"\bsr\.?\b")
_WORD = re.compile(r"^[a-z0-9]{1,3}$")


def normalize_phrase(text: str) -> str:
    """Lowercase, expand Sr., strip punctuation, collapse whitespace."""
    lowered = text.casefold()
    lowered = _SR.sub("senior", lowered)
    lowered = lowered.replace("&", " and ")
    collapsed = _NON_ALNUM.sub(" ", lowered)
    return " ".join(collapsed.split())


def _keyword_in_text(keyword: str, text: str) -> bool:
    needle = normalize_phrase(keyword)
    haystack = normalize_phrase(text)
    if not needle or not haystack:
        return False
    if _WORD.fullmatch(needle):
        return bool(re.search(rf"\b{re.escape(needle)}\b", haystack))
    return needle in haystack


def title_matches(title: str, patterns: list[str]) -> bool:
    normalized_title = normalize_phrase(title)
    if not normalized_title:
        return False
    for pattern in patterns:
        needle = normalize_phrase(pattern)
        if needle and re.search(rf"\b{re.escape(needle)}\b", normalized_title):
            return True
    return False


def _workplace_key(workplace_type: str | None) -> str:
    if not workplace_type:
        return ""
    return workplace_type.casefold().replace("-", "").replace(" ", "")


def location_blob(job: Job) -> str:
    parts = list(job.locations)
    if job.workplace_type:
        parts.append(job.workplace_type)
    return " ".join(parts)


def _matches_keywords(job: Job, keywords: list[str], *, include_workplace: bool = True) -> bool:
    blob = location_blob(job) if include_workplace else " ".join(job.locations)
    return any(_keyword_in_text(keyword, blob) for keyword in keywords)


def is_remote_job(job: Job, remote_keywords: list[str]) -> bool:
    wt = _workplace_key(job.workplace_type)
    if wt == "remote":
        return True
    if wt in {"hybrid", "onsite"}:
        return _matches_keywords(job, remote_keywords, include_workplace=False)
    if job.is_remote:
        return True
    return _matches_keywords(job, remote_keywords)


def location_matches(job: Job, locations: dict[str, list[str]]) -> bool:
    for region in ("bay_area", "los_angeles", "orange_county"):
        if _matches_keywords(job, locations.get(region) or []):
            return True
    return is_remote_job(job, locations.get("remote") or [])


def job_matches(
    job: Job,
    level_patterns: list[str],
    domain_patterns: list[str],
    locations: dict[str, list[str]],
) -> bool:
    return (
        title_matches(job.title, level_patterns)
        and title_matches(job.title, domain_patterns)
        and location_matches(job, locations)
    )
