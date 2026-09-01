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
