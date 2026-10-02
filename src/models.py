"""Normalized job posting."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from src.timestamps import parse_timestamp


@dataclass
class Job:
    ats: str
    slug: str
    job_id: str
    company: str
    title: str
    url: str
    locations: list[str] = field(default_factory=list)
    is_remote: bool = False
    workplace_type: str | None = None
    posted_at: datetime | None = None
    id: str = ""

    def __post_init__(self) -> None:
        self.job_id = str(self.job_id)
        if not self.id:
            self.id = f"{self.ats}:{self.slug}:{self.job_id}"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["posted_at"] = self.posted_at.isoformat() if self.posted_at else None
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Job:
        return cls(
            ats=str(data.get("ats") or ""),
            slug=str(data.get("slug") or ""),
            job_id=str(data.get("job_id") or ""),
            company=str(data.get("company") or ""),
            title=str(data.get("title") or ""),
            url=str(data.get("url") or ""),
            locations=list(data.get("locations") or []),
            is_remote=bool(data.get("is_remote")),
            workplace_type=data.get("workplace_type"),
            posted_at=parse_timestamp(data.get("posted_at")),
            id=str(data.get("id") or ""),
        )


@dataclass
class Company:
    name: str
    ats: str
    slug: str = ""
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)
