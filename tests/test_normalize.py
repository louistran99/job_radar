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


def test_gem_normalize_offices_and_location_types() -> None:
    payload = [
        {
            "id": "4965519002",
            "title": " Engineering Manager, Mobile ",
            "absolute_url": "https://jobs.gem.com/acme/4965519002",
            "location": {"name": "Global"},
            "location_type": "hybrid",
            "offices": [
                {
                    "name": "San Francisco",
                    "location": {"name": "San Francisco, United States"},
                }
            ],
        },
        {
            "id": "remote-1",
            "title": "Head of Mobile",
            "absolute_url": "https://jobs.gem.com/acme/remote-1",
            "location": {"name": "Remote — US"},
            "location_type": "remote",
            "offices": [],
        },
        {
            "id": "onsite-1",
            "title": "Director, Mobile Engineering",
            "absolute_url": "https://jobs.gem.com/acme/onsite-1",
            "location": {"name": "Los Angeles, United States"},
            "location_type": "in_office",
        },
    ]
    jobs = jobs_from_payload("gem", payload, _company("gem"))
    assert len(jobs) == 3

    hybrid = jobs[0]
    assert hybrid.id == "gem:acme:4965519002"
    assert hybrid.title == "Engineering Manager, Mobile"
    assert hybrid.locations == ["San Francisco, United States"]
    assert hybrid.workplace_type == "hybrid"
    assert hybrid.is_remote is False
    assert hybrid.url == "https://jobs.gem.com/acme/4965519002"

    remote = jobs[1]
    assert remote.workplace_type == "remote"
    assert remote.is_remote is True
    assert remote.locations == ["Remote — US"]

    onsite = jobs[2]
    assert onsite.workplace_type == "onsite"
    assert onsite.is_remote is False
    assert onsite.locations == ["Los Angeles, United States"]


def test_gem_skips_missing_id_and_title() -> None:
    payload = [
        {"title": "Engineering Manager, Mobile", "absolute_url": "https://jobs.gem.com/acme/x"},
        {"id": "no-title", "title": "  ", "absolute_url": "https://jobs.gem.com/acme/y"},
        {
            "id": "ok",
            "title": "Engineering Manager, Mobile",
            "absolute_url": "https://jobs.gem.com/acme/ok",
            "location_type": "on_site",
            "offices": [{"name": "NYC Office"}],
        },
        {"jobs": "not-a-list-item"},
    ]
    jobs = jobs_from_payload("gem", payload, _company("gem"))
    assert len(jobs) == 1
    assert jobs[0].id == "gem:acme:ok"
    assert jobs[0].workplace_type == "onsite"
    assert jobs[0].locations == ["NYC Office"]


def test_gem_non_list_payload_is_empty() -> None:
    assert jobs_from_payload("gem", {"jobs": []}, _company("gem")) == []
