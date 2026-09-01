from __future__ import annotations

from pathlib import Path

from src.models import Job
from src.snapshot import diff_snapshots, load_snapshot, merge_current_with_previous, save_snapshot


def _job(job_id: str, title: str = "Engineering Manager, Mobile") -> Job:
    return Job(
        ats="greenhouse",
        slug="acme",
        job_id=job_id,
        company="Acme",
        title=title,
        url=f"https://example.com/{job_id}",
        locations=["San Francisco, CA"],
    )


def test_first_run_is_baseline_not_all_new() -> None:
    current = {j.id: j for j in [_job("1"), _job("2")]}
    diff = diff_snapshots({}, current)
    assert diff.baseline is True
    assert diff.new == []
    assert diff.removed == []
    assert {j.job_id for j in diff.still_open} == {"1", "2"}


def test_subsequent_run_new_removed_still_open() -> None:
    previous = {j.id: j for j in [_job("1"), _job("2")]}
    current = {j.id: j for j in [_job("2"), _job("3")]}
    diff = diff_snapshots(previous, current)
    assert diff.baseline is False
    assert [j.job_id for j in diff.new] == ["3"]
    assert [j.job_id for j in diff.removed] == ["1"]
    assert [j.job_id for j in diff.still_open] == ["2"]


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.json"
    jobs = {j.id: j for j in [_job("1")]}
    save_snapshot(path, jobs)
    loaded = load_snapshot(path)
    assert set(loaded) == set(jobs)
    assert loaded[_job("1").id].title == "Engineering Manager, Mobile"


def test_missing_snapshot_is_empty(tmp_path: Path) -> None:
    assert load_snapshot(tmp_path / "nope.json") == {}


def test_merge_carries_forward_failed_company_jobs() -> None:
    previous = {
        "greenhouse:acme:1": _job("1"),
        "greenhouse:other:9": Job(
            ats="greenhouse",
            slug="other",
            job_id="9",
            company="Other",
            title="Head of Mobile",
            url="https://example.com/9",
            locations=["Remote"],
        ),
    }
    fetched = {"greenhouse:acme:2": _job("2")}
    merged = merge_current_with_previous(
        previous, fetched, failed_company_keys={("greenhouse", "other")}
    )
    assert "greenhouse:acme:2" in merged
    assert "greenhouse:other:9" in merged
    assert "greenhouse:acme:1" not in merged
