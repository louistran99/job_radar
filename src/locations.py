"""Location string helpers shared by ATS normalizers."""

from __future__ import annotations

import re

_SPLIT = re.compile(r"\s*[;|]\s*|\s+/\s+|\s+\band\s+\b", re.IGNORECASE)


def split_location_text(text: str) -> list[str]:
    """Split a location blob on ; | / and 'and', not on commas."""
    stripped = text.strip()
    if not stripped:
        return []
    parts = [part.strip() for part in _SPLIT.split(stripped) if part.strip()]
    return parts or [stripped]


def dedupe_locations(locations: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for loc in locations:
        key = loc.casefold()
        if not loc or key in seen:
            continue
        seen.add(key)
        result.append(loc)
    return result


_WORKPLACE_ALIASES = {
    "remote": "remote",
    "hybrid": "hybrid",
    "onsite": "onsite",
    "inoffice": "onsite",
}


def normalize_workplace_type(value: object) -> str | None:
    """Map a board's workplace string to remote, hybrid, onsite, or None.

    Case, spaces, hyphens, and underscores are ignored, so `OnSite`, `on-site`,
    and `on_site` all give `onsite`. Anything unrecognized (`unspecified`,
    `flexible`) gives None.
    """
    if value is None:
        return None
    key = re.sub(r"[\s_-]+", "", str(value).casefold())
    return _WORKPLACE_ALIASES.get(key)


def join_location_parts(parts: list[str]) -> str:
    """Join city/region/country fragments, dropping blanks and repeats."""
    return ", ".join(dedupe_locations([part.strip() for part in parts]))
