from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.models import Company, Job
from src.normalize import jobs_from_payload
from src.snapshot import load_snapshot, save_snapshot
from src.timestamps import parse_timestamp


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-01T04:54:45.327Z", _utc(2026, 10, 1, 4, 54, 45, 327000)),
        ("2026-09-09T10:50:29-04:00", _utc(2026, 9, 9, 14, 50, 29)),
        ("2026-08-24T14:44:49.699+00:00", _utc(2026, 8, 24, 14, 44, 49, 699000)),
        ("2026-09-18 13:27:28 UTC", _utc(2026, 9, 18, 13, 27, 28)),
        ("2026-07-30", _utc(2026, 7, 30)),
        ("2026-09-18T13:27:28.1234567Z", _utc(2026, 9, 18, 13, 27, 28, 123456)),
        (1786469891368, _utc(2026, 8, 11, 17, 38, 11, 368000)),
        ("1786469891368", _utc(2026, 8, 11, 17, 38, 11, 368000)),
        (1786469891, _utc(2026, 8, 11, 17, 38, 11)),
        ("2026-09-18T13:27:28", _utc(2026, 9, 18, 13, 27, 28)),
    ],
)
def test_parse_timestamp_formats(value: object, expected: datetime) -> None:
    assert parse_timestamp(value) == expected


@pytest.mark.parametrize("value", [None, "", "   ", "not a date", True, {}, []])
def test_parse_timestamp_returns_none_for_unusable_values(value: object) -> None:
    assert parse_timestamp(value) is None


def _company(ats: str, slug: str = "acme") -> Company:
    return Company(name="Acme", ats=ats, slug=slug)


def test_adapters_map_the_board_publish_field() -> None:
    cases = [
        (
            "greenhouse",
            {
                "jobs": [
                    {
                        "id": 1,
                        "title": "Engineering Manager",
                        "first_published": "2026-09-09T10:50:29-04:00",
                        "updated_at": "2026-09-25T16:45:00-04:00",
                    }
                ]
            },
            _utc(2026, 9, 9, 14, 50, 29),
        ),
        (
            "lever",
            [{"id": "a", "text": "Engineering Manager", "createdAt": 1786469891368}],
            _utc(2026, 8, 11, 17, 38, 11, 368000),
        ),
        (
            "ashby",
            {
                "jobs": [
                    {
                        "id": "a",
                        "title": "Engineering Manager",
                        "publishedAt": "2026-08-24T14:44:49.699+00:00",
                    }
                ]
            },
            _utc(2026, 8, 24, 14, 44, 49, 699000),
        ),
        (
            "gem",
            [
                {
                    "id": "a",
                    "title": "Engineering Manager",
                    "first_published_at": "2020-11-17T15:37:23.000Z",
                    "updated_at": "2026-03-10T21:20:54.077Z",
                }
            ],
            _utc(2020, 11, 17, 15, 37, 23),
        ),
        (
            "smartrecruiters",
            {
                "content": [
                    {
                        "id": "1",
                        "name": "Engineering Manager",
                        "releasedDate": "2026-10-01T04:54:45.327Z",
                    }
                ]
            },
            _utc(2026, 10, 1, 4, 54, 45, 327000),
        ),
        (
            "workable",
            {
                "jobs": [
                    {
                        "shortcode": "AB12",
                        "title": "Engineering Manager",
                        "published_on": "2026-07-30",
                        "created_at": "2026-07-01",
                    }
                ]
            },
            _utc(2026, 7, 30),
        ),
        (
            "recruitee",
            {
                "offers": [
                    {
                        "id": 1,
                        "title": "Engineering Manager",
                        "status": "published",
                        "published_at": "2026-09-18 13:27:28 UTC",
                        "updated_at": "2026-10-01 14:29:22 UTC",
                    }
                ]
            },
            _utc(2026, 9, 18, 13, 27, 28),
        ),
    ]
    for ats, payload, expected in cases:
        jobs = jobs_from_payload(ats, payload, _company(ats))
        assert len(jobs) == 1, ats
        assert jobs[0].posted_at == expected, ats


def test_personio_and_bamboohr_have_no_posted_at() -> None:
    personio = jobs_from_payload(
        "personio",
        [{"id": 1, "name": "Engineering Manager", "offices": ["Berlin"]}],
        _company("personio"),
    )
    bamboohr = jobs_from_payload(
        "bamboohr",
        {"result": [{"id": "1", "jobOpeningName": "Engineering Manager"}]},
        _company("bamboohr"),
    )
    assert personio[0].posted_at is None
    assert bamboohr[0].posted_at is None


def test_missing_or_bad_publish_field_leaves_posted_at_none() -> None:
    payload = [
        {"id": "a", "text": "Engineering Manager"},
        {"id": "b", "text": "Engineering Manager", "createdAt": "garbage"},
    ]
    jobs = jobs_from_payload("lever", payload, _company("lever"))
    assert [job.posted_at for job in jobs] == [None, None]


def test_job_dict_round_trips_posted_at() -> None:
    posted = _utc(2026, 9, 9, 14, 50, 29)
    job = Job(
        ats="greenhouse",
        slug="acme",
        job_id="1",
        company="Acme",
        title="Engineering Manager",
        url="https://example.com/1",
        posted_at=posted,
    )
    data = job.to_dict()
    assert data["posted_at"] == "2026-09-09T14:50:29+00:00"
    assert Job.from_dict(data).posted_at == posted

    without = Job.from_dict({**data, "posted_at": None})
    assert without.posted_at is None
    assert Job.from_dict({k: v for k, v in data.items() if k != "posted_at"}).posted_at is None


def test_snapshot_round_trips_posted_at(tmp_path) -> None:
    posted = _utc(2026, 9, 9, 14, 50, 29)
    job = Job(
        ats="greenhouse",
        slug="acme",
        job_id="1",
        company="Acme",
        title="Engineering Manager",
        url="https://example.com/1",
        posted_at=posted,
    )
    path = tmp_path / "snapshot.json"
    save_snapshot(path, {job.id: job})
    assert load_snapshot(path)[job.id].posted_at == posted
