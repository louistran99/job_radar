from __future__ import annotations

import pytest

from src.locations import normalize_workplace_type
from src.models import Company
from src.normalize import jobs_from_payload


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("remote", "remote"),
        ("Remote", "remote"),
        ("hybrid", "hybrid"),
        ("Hybrid", "hybrid"),
        ("onsite", "onsite"),
        ("OnSite", "onsite"),
        ("on-site", "onsite"),
        ("on_site", "onsite"),
        ("On Site", "onsite"),
        ("in_office", "onsite"),
        ("  remote  ", "remote"),
        ("unspecified", None),
        ("flexible", None),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_normalize_workplace_type(value: object, expected: str | None) -> None:
    assert normalize_workplace_type(value) == expected


def _company(ats: str) -> Company:
    return Company(name="Acme", ats=ats, slug="acme")


def test_lever_ashby_gem_emit_only_enum_values() -> None:
    lever = jobs_from_payload(
        "lever",
        [
            {"id": "1", "text": "EM", "workplaceType": "on-site"},
            {"id": "2", "text": "EM", "workplaceType": "unspecified"},
            {"id": "3", "text": "EM", "workplaceType": "remote"},
            {"id": "4", "text": "EM"},
        ],
        _company("lever"),
    )
    assert [job.workplace_type for job in lever] == ["onsite", None, "remote", None]
    assert [job.is_remote for job in lever] == [False, False, True, False]

    ashby = jobs_from_payload(
        "ashby",
        {
            "jobs": [
                {"id": "1", "title": "EM", "workplaceType": "OnSite"},
                {"id": "2", "title": "EM", "workplaceType": "Hybrid", "isRemote": True},
                {"id": "3", "title": "EM", "workplaceType": "Remote"},
                {"id": "4", "title": "EM", "workplaceType": "Unknown"},
            ]
        },
        _company("ashby"),
    )
    assert [job.workplace_type for job in ashby] == ["onsite", "hybrid", "remote", None]
    # isRemote is kept on the Python model even when it disagrees with workplace_type.
    assert ashby[1].is_remote is True

    gem = jobs_from_payload(
        "gem",
        [
            {"id": "1", "title": "EM", "location_type": "in_office"},
            {"id": "2", "title": "EM", "location_type": "on-site"},
            {"id": "3", "title": "EM", "location_type": "Hybrid"},
            {"id": "4", "title": "EM", "location_type": "unspecified"},
            {"id": "5", "title": "EM", "location_type": "remote"},
        ],
        _company("gem"),
    )
    assert [job.workplace_type for job in gem] == [
        "onsite",
        "onsite",
        "hybrid",
        None,
        "remote",
    ]
