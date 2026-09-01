"""Load/save matched-job snapshots and diff against the previous run."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.models import Job


@dataclass
class Diff:
    new: list[Job]
    removed: list[Job]
    still_open: list[Job]
    baseline: bool


def load_snapshot(path: Path) -> dict[str, Job]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    raw_jobs = data.get("jobs", {})
    jobs: dict[str, Job] = {}
    if isinstance(raw_jobs, dict):
        items = raw_jobs.values()
    elif isinstance(raw_jobs, list):
        items = raw_jobs
    else:
        return {}
    for item in items:
        if not isinstance(item, dict):
            continue
        job = Job.from_dict(item)
        if job.id:
            jobs[job.id] = job
    return jobs


def save_snapshot(path: Path, jobs: dict[str, Job], *, generated_at: datetime | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    stamp = generated_at or datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "generated_at": stamp.isoformat(),
        "jobs": {job_id: job.to_dict() for job_id, job in sorted(jobs.items())},
    }
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def diff_snapshots(previous: dict[str, Job], current: dict[str, Job]) -> Diff:
    if not previous:
        return Diff(
            new=[],
            removed=[],
            still_open=sorted(current.values(), key=_sort_key),
            baseline=True,
        )
    prev_ids = set(previous)
    curr_ids = set(current)
    new_ids = curr_ids - prev_ids
    removed_ids = prev_ids - curr_ids
    still_ids = curr_ids & prev_ids
    return Diff(
        new=sorted((current[i] for i in new_ids), key=_sort_key),
        removed=sorted((previous[i] for i in removed_ids), key=_sort_key),
        still_open=sorted((current[i] for i in still_ids), key=_sort_key),
        baseline=False,
    )


def merge_current_with_previous(
    previous: dict[str, Job],
    fetched: dict[str, Job],
    failed_company_keys: set[tuple[str, str]],
) -> dict[str, Job]:
    """Keep previous jobs for companies that errored (not 404) this run."""
    merged = dict(fetched)
    for job_id, job in previous.items():
        key = (job.ats, job.slug)
        if key in failed_company_keys and job_id not in merged:
            merged[job_id] = job
    return merged


def _sort_key(job: Job) -> tuple[str, str, str]:
    return (job.company.casefold(), job.title.casefold(), job.id)
