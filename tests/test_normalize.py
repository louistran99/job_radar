from __future__ import annotations

from src.models import Company
from src.normalize import jobs_from_payload


def _company(ats: str, slug: str = "acme") -> Company:
    return Company(name="Acme", ats=ats, slug=slug)


def test_greenhouse_normalize_title_and_location() -> None:
    payload = {
        "jobs": [
            {
                "id": 8023928,
                "title": "Engineering Manager, Mobile",
                "location": {"name": "San Francisco, CA; Remote"},
                "absolute_url": "https://example.com/8023928",
            }
        ]
    }
    jobs = jobs_from_payload("greenhouse", payload, _company("greenhouse"))
    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == "greenhouse:acme:8023928"
    assert job.title == "Engineering Manager, Mobile"
    assert job.locations == ["San Francisco, CA", "Remote"]
    assert job.is_remote is True
    assert job.url.endswith("8023928")


def test_lever_bare_array_and_all_locations() -> None:
    payload = [
        {
            "id": "abc-123",
            "text": "Director, Mobile Engineering",
            "categories": {
                "location": "New York",
                "allLocations": ["New York", "Remote"],
            },
            "workplaceType": "hybrid",
            "hostedUrl": "https://jobs.lever.co/acme/abc-123",
        }
    ]
    jobs = jobs_from_payload("lever", payload, _company("lever"))
    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == "lever:acme:abc-123"
    assert job.title == "Director, Mobile Engineering"
    assert "Remote" in job.locations
    assert job.workplace_type == "hybrid"


def test_ashby_skips_unlisted_and_trims_title() -> None:
    payload = {
        "jobs": [
            {
                "id": "hidden",
                "title": "Engineering Manager, Mobile",
                "location": "San Francisco",
                "isListed": False,
                "jobUrl": "https://jobs.ashbyhq.com/acme/hidden",
            },
            {
                "id": "shown",
                "title": " Engineering Manager, Mobile",
                "location": "New York, NY (HQ)",
                "secondaryLocations": [{"location": "Remote (US)"}],
                "isRemote": True,
                "workplaceType": "Hybrid",
                "isListed": True,
                "jobUrl": "https://jobs.ashbyhq.com/acme/shown",
            },
        ]
    }
    jobs = jobs_from_payload("ashby", payload, _company("ashby"))
    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == "ashby:acme:shown"
    assert job.title == "Engineering Manager, Mobile"
    assert job.locations[0] == "New York, NY (HQ)"
    assert "Remote (US)" in job.locations
    assert job.is_remote is True
    assert job.workplace_type == "Hybrid"
