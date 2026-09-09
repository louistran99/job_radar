from __future__ import annotations

from pathlib import Path

import pytest

from src.config import JobsConfig
from src.models import Company, Job
from tests.fakes import FakeFetcher

from src.cli import run

LEVEL = ["engineering manager", "head of"]
DOMAIN = ["mobile"]
LOCATIONS = {
    "bay_area": ["san francisco"],
    "los_angeles": ["los angeles"],
    "orange_county": ["irvine"],
    "remote": ["remote"],
}


def _config(companies: list[Company]) -> JobsConfig:
    return JobsConfig(
        sources={
            "greenhouse": {
                "enabled": True,
                "url": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
            }
        },
        companies=companies,
        level_patterns=LEVEL,
        domain_patterns=DOMAIN,
        locations=LOCATIONS,
        delay_seconds=0,
    )


def _job(slug: str, job_id: str, title: str, location: str) -> Job:
    return Job(
        ats="greenhouse",
        slug=slug,
        job_id=job_id,
        company=slug.title(),
        title=title,
        url=f"https://example.com/{job_id}",
        locations=[location],
        is_remote="remote" in location.casefold(),
    )


def test_first_run_writes_baseline_not_new(tmp_path: Path) -> None:
    companies = [Company(name="Acme", ats="greenhouse", slug="acme")]
    job = _job("acme", "1", "Engineering Manager, Mobile", "San Francisco, CA")
    fetcher = FakeFetcher(jobs={("greenhouse", "acme"): [job]})
    snapshot = tmp_path / "snapshot.json"
    report = tmp_path / "report.md"
    code = run(_config(companies), fetcher, snapshot, report, delay_seconds=0)
    assert code == 0
    text = report.read_text(encoding="utf-8")
    assert "Baseline" in text
    assert "## New" not in text
    assert "Engineering Manager, Mobile" in text
    assert snapshot.exists()


def test_second_run_reports_new_and_removed(tmp_path: Path) -> None:
    companies = [Company(name="Acme", ats="greenhouse", slug="acme")]
    first = _job("acme", "1", "Engineering Manager, Mobile", "San Francisco, CA")
    second = _job("acme", "2", "Head of Mobile", "San Francisco, CA")
    snapshot = tmp_path / "snapshot.json"
    report = tmp_path / "report.md"
    config = _config(companies)
    run(
        config,
        FakeFetcher(jobs={("greenhouse", "acme"): [first]}),
        snapshot,
        report,
        delay_seconds=0,
    )
    code = run(
        config,
        FakeFetcher(jobs={("greenhouse", "acme"): [second]}),
        snapshot,
        report,
        delay_seconds=0,
    )
    assert code == 0
    text = report.read_text(encoding="utf-8")
    assert "## New (1)" in text
    assert "Head of Mobile" in text
    assert "## Removed (1)" in text
    assert "Engineering Manager, Mobile" in text


def test_404_skip_still_writes_report(tmp_path: Path) -> None:
    companies = [
        Company(name="Acme", ats="greenhouse", slug="acme"),
        Company(name="Nope", ats="greenhouse", slug="nope"),
    ]
    job = _job("acme", "1", "Engineering Manager, Mobile", "Remote")
    fetcher = FakeFetcher(
        jobs={("greenhouse", "acme"): [job]},
        missing={("greenhouse", "nope")},
    )
    snapshot = tmp_path / "snapshot.json"
    report = tmp_path / "report.md"
    code = run(_config(companies), fetcher, snapshot, report, delay_seconds=0)
    assert code == 0
    assert "Acme" in report.read_text(encoding="utf-8")
    assert fetcher.calls[0].slug == "acme"
    assert fetcher.calls[1].slug == "nope"


def test_fetch_error_carries_forward_previous_jobs(tmp_path: Path) -> None:
    companies = [Company(name="Acme", ats="greenhouse", slug="acme")]
    job = _job("acme", "1", "Engineering Manager, Mobile", "San Francisco, CA")
    snapshot = tmp_path / "snapshot.json"
    report = tmp_path / "report.md"
    config = _config(companies)
    run(
        config,
        FakeFetcher(jobs={("greenhouse", "acme"): [job]}),
        snapshot,
        report,
        delay_seconds=0,
    )
    code = run(
        config,
        FakeFetcher(errors={("greenhouse", "acme"): "500 from upstream"}),
        snapshot,
        report,
        delay_seconds=0,
    )
    assert code == 0
    text = report.read_text(encoding="utf-8")
    assert "## Removed (0)" in text
    assert "Engineering Manager, Mobile" in text


def test_validate_only_does_not_write_snapshot(tmp_path: Path) -> None:
    companies = [Company(name="Acme", ats="greenhouse", slug="acme")]
    snapshot = tmp_path / "snapshot.json"
    report = tmp_path / "report.md"
    code = run(
        _config(companies),
        FakeFetcher(jobs={("greenhouse", "acme"): []}),
        snapshot,
        report,
        validate_only=True,
        delay_seconds=0,
    )
    assert code == 0
    assert not snapshot.exists()
    assert not report.exists()


def test_non_matching_titles_are_excluded(tmp_path: Path) -> None:
    companies = [Company(name="Acme", ats="greenhouse", slug="acme")]
    jobs = [
        _job("acme", "1", "Staff iOS Engineer", "San Francisco, CA"),
        _job("acme", "2", "Engineering Manager, Mobile", "New York, NY"),
    ]
    snapshot = tmp_path / "snapshot.json"
    report = tmp_path / "report.md"
    run(
        _config(companies),
        FakeFetcher(jobs={("greenhouse", "acme"): jobs}),
        snapshot,
        report,
        delay_seconds=0,
    )
    text = report.read_text(encoding="utf-8")
    assert "Staff iOS Engineer" not in text
    assert "Engineering Manager, Mobile" not in text
    assert "Baseline run — 0 matched job(s)" in text


def test_verbose_logs_fetched_and_matched(tmp_path: Path, caplog) -> None:
    companies = [Company(name="Acme", ats="greenhouse", slug="acme")]
    jobs = [
        _job("acme", "1", "Staff iOS Engineer", "San Francisco, CA"),
        _job("acme", "2", "Engineering Manager, Mobile", "San Francisco, CA"),
    ]
    snapshot = tmp_path / "snapshot.json"
    report = tmp_path / "report.md"
    with caplog.at_level("DEBUG"):
        run(
            _config(companies),
            FakeFetcher(jobs={("greenhouse", "acme"): jobs}),
            snapshot,
            report,
            delay_seconds=0,
        )
    messages = caplog.messages
    assert "Acme: 2 job(s) fetched, 1 matched" in messages
    assert any(
        "matched: Acme — Engineering Manager, Mobile [San Francisco, CA]" in m
        for m in messages
    )
    assert not any("Staff iOS Engineer" in m for m in messages)
    assert "Fetched 2 job(s) from 1 board(s); 1 matched filters" in messages


def test_run_progress_callback_is_optional_and_quiet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    companies = [Company(name="Acme", ats="greenhouse", slug="acme")]
    job = _job("acme", "1", "Engineering Manager, Mobile", "San Francisco, CA")
    run(
        _config(companies),
        FakeFetcher(jobs={("greenhouse", "acme"): [job]}),
        tmp_path / "snapshot.json",
        tmp_path / "report.md",
        delay_seconds=0,
    )
    assert capsys.readouterr().out == ""


def test_run_reports_fetch_progress(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    companies = [Company(name="Acme", ats="greenhouse", slug="acme")]
    job = _job("acme", "1", "Engineering Manager, Mobile", "San Francisco, CA")
    seen: list[tuple[int, str]] = []
    run(
        _config(companies),
        FakeFetcher(jobs={("greenhouse", "acme"): [job]}),
        tmp_path / "snapshot.json",
        tmp_path / "report.md",
        delay_seconds=0,
        on_progress=lambda step, description: seen.append((step, description)),
    )
    assert seen == [
        (4, "Fetch and match jobs"),
        (5, "Write snapshot and report"),
    ]
    assert capsys.readouterr().out == "fetch Acme — 1/1\n"
