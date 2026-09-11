"""Normalized job posting."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


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
    id: str = ""

    def __post_init__(self) -> None:
        self.job_id = str(self.job_id)
        if not self.id:
            self.id = f"{self.ats}:{self.slug}:{self.job_id}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

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
            id=str(data.get("id") or ""),
        )


@dataclass
class Company:
    name: str
    ats: str
    slug: str = ""
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)
