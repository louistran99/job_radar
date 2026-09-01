"""Markdown report + stdout summary (future email body)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from src.models import Job
from src.snapshot import Diff

PACIFIC = ZoneInfo("America/Los_Angeles")


def _when(now: datetime | None = None) -> datetime:
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(PACIFIC)


def _job_line(job: Job) -> str:
    location = ", ".join(job.locations) if job.locations else "Location n/a"
    title = job.title
    if job.url:
        title = f"[{job.title}]({job.url})"
    return f"- **{job.company}** — {title} — {location}"


def _section(heading: str, jobs: list[Job]) -> list[str]:
    lines = [f"## {heading} ({len(jobs)})", ""]
    if not jobs:
        lines.append("_None._")
        lines.append("")
        return lines
    for job in jobs:
        lines.append(_job_line(job))
    lines.append("")
    return lines


def render_report(
    diff: Diff,
    *,
    companies_fetched: int,
    boards_skipped: int,
    now: datetime | None = None,
) -> str:
    stamp = _when(now)
    header = f"# Job monitor — {stamp.strftime('%Y-%m-%d %H:%M %Z')}"
    lines = [
        header,
        "",
        f"Fetched {companies_fetched} company board(s); skipped {boards_skipped} missing slug(s).",
        "",
    ]
    if diff.baseline:
        lines.extend(
            [
                f"Baseline run — {len(diff.still_open)} matched job(s). "
                "Later runs report New / Removed / Still open.",
                "",
            ]
        )
        lines.extend(_section("Open roles", diff.still_open))
    else:
        lines.extend(_section("New", diff.new))
        lines.extend(_section("Removed", diff.removed))
        lines.extend(_section("Still open", diff.still_open))
    return "\n".join(lines).rstrip() + "\n"


def write_report(path: Path, markdown: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(markdown, encoding="utf-8")
    os.replace(tmp, path)


def stdout_summary(diff: Diff, report_path: Path) -> str:
    if diff.baseline:
        body = f"Baseline: {len(diff.still_open)} matched job(s)"
    else:
        body = (
            f"New: {len(diff.new)}  "
            f"Removed: {len(diff.removed)}  "
            f"Still open: {len(diff.still_open)}"
        )
    return f"{body}\nWrote {report_path}"
