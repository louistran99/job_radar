from __future__ import annotations

from src.match import is_remote_job, job_matches, location_matches, title_matches
from src.models import Job

PATTERNS = [
    "engineering manager, mobile",
    "mobile engineering manager",
    "em, mobile",
    "mobile em",
    "head of mobile",
    "director of mobile",
    "director, mobile engineering",
    "director, mobile",
    "mobile director",
]

LOCATIONS = {
    "bay_area": ["san francisco", "sf", "oakland", "palo alto"],
    "los_angeles": ["los angeles", "santa monica", "culver city"],
    "orange_county": ["irvine", "orange county", "newport beach"],
    "remote": ["remote", "work from home", "wfh"],
}


def _job(**kwargs: object) -> Job:
    values = {
        "ats": "greenhouse",
        "slug": "acme",
        "job_id": "1",
        "company": "Acme",
        "title": "Engineering Manager, Mobile",
        "url": "https://example.com/1",
        "locations": ["San Francisco, CA"],
        "is_remote": False,
        "workplace_type": None,
    }
    values.update(kwargs)
    return Job(**values)  # type: ignore[arg-type]


def test_sr_expands_and_matches_senior_em_mobile() -> None:
    assert title_matches("Sr. Engineering Manager, Mobile", PATTERNS)


def test_director_comma_mobile_engineering() -> None:
    assert title_matches("Director, Mobile Engineering", PATTERNS)


def test_head_of_mobile_engineering() -> None:
    assert title_matches("Head of Mobile Engineering", PATTERNS)


def test_does_not_match_every_mobile_title() -> None:
    assert not title_matches("Staff Mobile Engineer", PATTERNS)
    assert not title_matches("Senior iOS Engineer", PATTERNS)
    assert not title_matches("System Mobile Engineer", PATTERNS)


def test_sf_location_matches() -> None:
    job = _job(locations=["San Francisco, CA"])
    assert location_matches(job, LOCATIONS)


def test_irvine_matches_orange_county() -> None:
    job = _job(locations=["Irvine, CA"])
    assert location_matches(job, LOCATIONS)


def test_nyc_does_not_match() -> None:
    job = _job(locations=["New York, NY"], is_remote=False, workplace_type=None)
    assert not location_matches(job, LOCATIONS)


def test_remote_workplace_type_matches() -> None:
    job = _job(locations=["United States"], is_remote=False, workplace_type="Remote")
    assert is_remote_job(job, LOCATIONS["remote"])
    assert location_matches(job, LOCATIONS)


def test_ashby_hybrid_nyc_isremote_does_not_count_as_remote() -> None:
    job = _job(
        locations=["New York, NY"],
        is_remote=True,
        workplace_type="Hybrid",
    )
    assert not location_matches(job, LOCATIONS)


def test_sf_plus_remote_matches_once() -> None:
    job = _job(locations=["San Francisco, CA", "Remote"], is_remote=True)
    assert job_matches(job, PATTERNS, LOCATIONS)


def test_matching_title_in_nyc_is_rejected() -> None:
    job = _job(locations=["New York, NY"], is_remote=False)
    assert title_matches(job.title, PATTERNS)
    assert not job_matches(job, PATTERNS, LOCATIONS)


def test_sf_word_boundary_does_not_match_transform() -> None:
    job = _job(locations=["Transform HQ"], is_remote=False)
    assert not location_matches(job, LOCATIONS)
