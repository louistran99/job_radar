from __future__ import annotations

from src.models import Company
from src.validate import exit_code, validate_companies
from tests.fakes import FakeFetcher


def test_404_is_skipped_not_fatal() -> None:
    fetcher = FakeFetcher(missing={("greenhouse", "nope")})
    valid, skipped = validate_companies(
        fetcher, [Company(name="Nope", ats="greenhouse", slug="nope")]
    )
    assert valid == []
    assert len(skipped) == 1
    assert skipped[0][0].name == "Nope"
    assert "404" in skipped[0][1]


def test_mixed_valid_and_404() -> None:
    acme = Company(name="Acme", ats="greenhouse", slug="acme")
    nope = Company(name="Nope", ats="greenhouse", slug="nope")
    fetcher = FakeFetcher(jobs={("greenhouse", "acme"): []}, missing={("greenhouse", "nope")})
    valid, skipped = validate_companies(fetcher, [acme, nope])
    assert [c.name for c in valid] == ["Acme"]
    assert [c.name for c, _ in skipped] == ["Nope"]


def test_empty_enabled_list_is_nonzero() -> None:
    assert exit_code(companies=[]) == 1
    assert exit_code(companies=[Company(name="A", ats="greenhouse", slug="a")]) == 0
