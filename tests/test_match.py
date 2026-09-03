from __future__ import annotations

from src.match import is_remote_job, job_matches, location_matches, title_matches
from src.models import Job

LEVEL = [
    "engineering manager",
    "senior engineering manager",
    "head of",
    "director",
    "tech lead manager",
    "tlm",
    "em",
]
DOMAIN = [
    "mobile",
    "ios",
    "android",
    "app experience",
    "client",
    "consumer app",
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


def test_engineering_manager_mobile() -> None:
    assert title_matches("Engineering Manager, Mobile", LEVEL)
    assert title_matches("Engineering Manager, Mobile", DOMAIN)


def test_sr_expands_and_matches_senior_em_ios() -> None:
    assert title_matches("Sr. Engineering Manager, iOS", LEVEL)
    assert title_matches("Sr. Engineering Manager, iOS", DOMAIN)


def test_director_comma_mobile_engineering() -> None:
    assert title_matches("Director, Mobile Engineering", LEVEL)
    assert title_matches("Director, Mobile Engineering", DOMAIN)


def test_head_of_mobile() -> None:
    assert title_matches("Head of Mobile", LEVEL)
    assert title_matches("Head of Mobile", DOMAIN)


def test_tech_lead_manager_android() -> None:
    assert title_matches("Tech Lead Manager, Android", LEVEL)
    assert title_matches("Tech Lead Manager, Android", DOMAIN)


def test_tlm_consumer_app() -> None:
    assert title_matches("TLM, Consumer App", LEVEL)
    assert title_matches("TLM, Consumer App", DOMAIN)


def test_em_ios_word_boundary() -> None:
    assert title_matches("EM, iOS", LEVEL)
    assert title_matches("EM, iOS", DOMAIN)


def test_engineering_manager_app_experience() -> None:
    assert title_matches("Engineering Manager, App Experience", LEVEL)
    assert title_matches("Engineering Manager, App Experience", DOMAIN)


def test_does_not_match_level_without_domain() -> None:
    assert title_matches("Engineering Manager, Backend", LEVEL)
    assert not title_matches("Engineering Manager, Backend", DOMAIN)
    assert not job_matches(
        _job(title="Engineering Manager, Backend"), LEVEL, DOMAIN, LOCATIONS
    )


def test_does_not_match_domain_without_level() -> None:
    assert not title_matches("Staff Mobile Engineer", LEVEL)
    assert not title_matches("Senior iOS Engineer", LEVEL)
    assert title_matches("Staff Mobile Engineer", DOMAIN)
    assert title_matches("Senior iOS Engineer", DOMAIN)


def test_em_does_not_match_inside_system() -> None:
    assert not title_matches("System Mobile Engineer", LEVEL)
    assert title_matches("System Mobile Engineer", DOMAIN)


def test_director_of_engineering_platform_has_no_domain() -> None:
    assert title_matches("Director of Engineering, Platform", LEVEL)
    assert not title_matches("Director of Engineering, Platform", DOMAIN)


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
    assert job_matches(job, LEVEL, DOMAIN, LOCATIONS)


def test_matching_title_in_nyc_is_rejected() -> None:
    job = _job(locations=["New York, NY"], is_remote=False)
    assert title_matches(job.title, LEVEL)
    assert title_matches(job.title, DOMAIN)
    assert not job_matches(job, LEVEL, DOMAIN, LOCATIONS)


def test_sf_word_boundary_does_not_match_transform() -> None:
    job = _job(locations=["Transform HQ"], is_remote=False)
    assert not location_matches(job, LOCATIONS)
