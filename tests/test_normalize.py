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
    assert job.workplace_type == "hybrid"


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


def test_smartrecruiters_builds_url_and_cleans_full_location() -> None:
    payload = {
        "totalFound": 2,
        "content": [
            {
                "id": "744000152827243",
                "name": "Engineering Manager, Mobile",
                "location": {
                    "city": "bangalore",
                    "country": "in",
                    "remote": False,
                    "hybrid": False,
                    "fullLocation": "bangalore, , India",
                },
            },
            {
                "id": "744000152827244",
                "name": "Director, Mobile Engineering",
                "location": {
                    "city": "Lincolnshire",
                    "region": "IL",
                    "country": "us",
                    "remote": False,
                    "hybrid": True,
                    "fullLocation": "Lincolnshire, IL, United States",
                },
            },
        ],
    }
    jobs = jobs_from_payload(
        "smartrecruiters", payload, _company("smartrecruiters", "BoschGroup")
    )
    assert len(jobs) == 2

    bangalore = jobs[0]
    assert bangalore.id == "smartrecruiters:BoschGroup:744000152827243"
    assert bangalore.title == "Engineering Manager, Mobile"
    assert bangalore.locations == ["bangalore, India"]
    assert bangalore.workplace_type is None
    assert bangalore.is_remote is False
    assert bangalore.url == (
        "https://jobs.smartrecruiters.com/BoschGroup/744000152827243"
    )

    hybrid = jobs[1]
    assert hybrid.locations == ["Lincolnshire, IL, United States"]
    assert hybrid.workplace_type == "hybrid"


def test_smartrecruiters_falls_back_to_city_region_country() -> None:
    payload = {
        "content": [
            {
                "id": "1",
                "name": "Head of Mobile",
                "location": {"city": "Austin", "region": "TX", "remote": True},
            },
            {"name": "Engineering Manager, Mobile"},
            {"id": "2", "name": "   "},
        ]
    }
    jobs = jobs_from_payload("smartrecruiters", payload, _company("smartrecruiters"))
    assert len(jobs) == 1
    assert jobs[0].locations == ["Austin, TX"]
    assert jobs[0].workplace_type == "remote"
    assert jobs[0].is_remote is True


def test_workable_uses_shortcode_and_telecommuting() -> None:
    payload = {
        "name": "Hugging Face",
        "jobs": [
            {
                "title": "Engineering Manager, Mobile - US Remote",
                "shortcode": "002470F128",
                "telecommuting": True,
                "url": "https://apply.workable.com/j/002470F128",
                "country": "United States",
                "city": "New York",
                "state": "New York",
                "locations": [
                    {
                        "country": "United States",
                        "countryCode": "US",
                        "city": "New York",
                        "region": "New York",
                    }
                ],
            },
            {
                "title": "Director, Mobile Engineering",
                "shortcode": "81B46579FE",
                "telecommuting": False,
                "shortlink": "https://apply.workable.com/j/81B46579FE",
                "country": "France",
                "city": "Paris",
                "state": "Île-de-France",
                "locations": [],
            },
        ],
    }
    jobs = jobs_from_payload("workable", payload, _company("workable", "huggingface"))
    assert len(jobs) == 2

    remote = jobs[0]
    assert remote.id == "workable:huggingface:002470F128"
    # city and region are both "New York"; the repeat is dropped.
    assert remote.locations == ["New York, United States"]
    assert remote.is_remote is True
    assert remote.workplace_type == "remote"
    assert remote.url == "https://apply.workable.com/j/002470F128"

    onsite = jobs[1]
    assert onsite.locations == ["Paris, Île-de-France, France"]
    assert onsite.is_remote is False
    assert onsite.workplace_type is None
    assert onsite.url == "https://apply.workable.com/j/81B46579FE"


def test_recruitee_skips_unpublished_and_maps_workplace() -> None:
    payload = {
        "offers": [
            {
                "id": 1,
                "title": "Engineering Manager, Mobile",
                "status": "draft",
                "careers_url": "https://jobs.channable.com/o/draft",
            },
            {
                "id": 2751915,
                "title": "Director, Mobile Engineering",
                "status": "published",
                "careers_url": "https://jobs.channable.com/o/director-mobile",
                "location": "Utrecht, Utrecht, Netherlands",
                "city": "Utrecht",
                "country": "Netherlands",
                "remote": False,
                "hybrid": True,
                "on_site": False,
                "locations": [
                    {
                        "name": "Utrecht",
                        "city": "Utrecht",
                        "state": "Utrecht",
                        "country": "Netherlands",
                    }
                ],
            },
        ]
    }
    jobs = jobs_from_payload("recruitee", payload, _company("recruitee", "channable"))
    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == "recruitee:channable:2751915"
    assert job.locations == ["Utrecht, Netherlands"]
    assert job.workplace_type == "hybrid"
    assert job.is_remote is False
    assert job.url == "https://jobs.channable.com/o/director-mobile"


def test_recruitee_remote_falls_back_to_location_string() -> None:
    payload = {
        "offers": [
            {
                "id": 9,
                "title": "Head of Mobile",
                "status": "published",
                "careers_apply_url": "https://jobs.bunq.com/o/head-of-mobile/c/new",
                "location": "Remote, Netherlands",
                "remote": True,
            }
        ]
    }
    jobs = jobs_from_payload("recruitee", payload, _company("recruitee", "bunq"))
    assert len(jobs) == 1
    assert jobs[0].locations == ["Remote, Netherlands"]
    assert jobs[0].workplace_type == "remote"
    assert jobs[0].is_remote is True
    assert jobs[0].url == "https://jobs.bunq.com/o/head-of-mobile/c/new"


def test_personio_builds_url_from_offices() -> None:
    payload = [
        {
            "id": 2415353,
            "name": "Engineering Manager, Mobile",
            "office": "Berlin,Frankfurt am Main",
            "offices": ["Berlin", "Frankfurt am Main"],
            "department": "Group - Marketing",
        },
        {
            "id": 2377588,
            "name": "Director, Mobile Engineering",
            "office": "Remote",
            "offices": ["Remote"],
        },
        {"name": "Head of Mobile"},
    ]
    jobs = jobs_from_payload("personio", payload, _company("personio", "clark"))
    assert len(jobs) == 2

    berlin = jobs[0]
    assert berlin.id == "personio:clark:2415353"
    assert berlin.locations == ["Berlin", "Frankfurt am Main"]
    assert berlin.is_remote is False
    assert berlin.url == "https://clark.jobs.personio.de/job/2415353"

    remote = jobs[1]
    assert remote.locations == ["Remote"]
    assert remote.is_remote is True
    assert remote.workplace_type == "remote"


def test_personio_splits_office_string_when_offices_missing() -> None:
    payload = [
        {
            "id": 342554,
            "name": " Engineering Manager, Mobile ",
            "office": "Berlin,Zürich",
        }
    ]
    jobs = jobs_from_payload("personio", payload, _company("personio", "clark"))
    assert jobs[0].title == "Engineering Manager, Mobile"
    assert jobs[0].locations == ["Berlin", "Zürich"]


def test_bamboohr_maps_location_type_and_builds_url() -> None:
    payload = {
        "meta": {"totalCount": 3},
        "result": [
            {
                "id": "35",
                "jobOpeningName": "Engineering Manager, Mobile",
                "location": {"city": None, "state": None},
                "atsLocation": {
                    "country": None,
                    "state": None,
                    "province": None,
                    "city": None,
                },
                "isRemote": None,
                "locationType": "1",
            },
            {
                "id": "60",
                "jobOpeningName": "Director, Mobile Engineering ",
                "location": {"city": "chicago", "state": "Illinois"},
                "atsLocation": {
                    "country": None,
                    "state": None,
                    "province": None,
                    "city": None,
                },
                "locationType": "2",
            },
            {
                "id": "61",
                "jobOpeningName": "Head of Mobile",
                "location": {"city": "Dubai", "state": None},
                "locationType": "0",
            },
        ],
    }
    jobs = jobs_from_payload("bamboohr", payload, _company("bamboohr", "flyio"))
    assert len(jobs) == 3

    remote = jobs[0]
    assert remote.id == "bamboohr:flyio:35"
    # A fully remote opening with no region still reports remote via workplace_type.
    assert remote.locations == []
    assert remote.workplace_type == "remote"
    assert remote.is_remote is True
    assert remote.url == "https://flyio.bamboohr.com/careers/35"

    hybrid = jobs[1]
    assert hybrid.title == "Director, Mobile Engineering"
    assert hybrid.locations == ["chicago, Illinois"]
    assert hybrid.workplace_type == "hybrid"
    assert hybrid.is_remote is False

    onsite = jobs[2]
    assert onsite.locations == ["Dubai"]
    assert onsite.workplace_type == "onsite"


def test_bamboohr_remote_region_comes_from_ats_location() -> None:
    payload = {
        "result": [
            {
                "id": "7",
                "jobOpeningName": "Engineering Manager, Mobile",
                "location": {"city": None, "state": None},
                "atsLocation": {
                    "country": "Poland",
                    "state": None,
                    "province": "Poland",
                    "city": "Poland",
                },
                "locationType": "1",
            }
        ]
    }
    jobs = jobs_from_payload("bamboohr", payload, _company("bamboohr", "bitcoin"))
    assert jobs[0].locations == ["Poland"]
    assert jobs[0].workplace_type == "remote"


def test_new_adapters_ignore_wrong_shaped_payloads() -> None:
    company = _company("smartrecruiters")
    assert jobs_from_payload("smartrecruiters", [], company) == []
    assert jobs_from_payload("workable", [], _company("workable")) == []
    assert jobs_from_payload("recruitee", [], _company("recruitee")) == []
    assert jobs_from_payload("personio", {"jobs": []}, _company("personio")) == []
    assert jobs_from_payload("bamboohr", [], _company("bamboohr")) == []
