"""Timestamp parsing shared by ATS normalizers and the Job model."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

_EPOCH_MS_THRESHOLD = 100_000_000_000
_DIGITS = re.compile(r"^\d+$")
_FRACTION = re.compile(r"\.(\d+)")


def _from_epoch(value: float) -> datetime | None:
    seconds = value / 1000 if abs(value) >= _EPOCH_MS_THRESHOLD else value
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _pad_fraction(match: re.Match[str]) -> str:
    return "." + match.group(1)[:6].ljust(6, "0")


def parse_timestamp(value: Any) -> datetime | None:
    """Parse a board timestamp into an aware UTC datetime, or None.

    Accepts ISO 8601 (with `Z` or an offset), `2026-09-18 13:27:28 UTC`,
    date-only strings (midnight UTC), and epoch seconds or milliseconds.
    Naive values are read as UTC.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        return _from_epoch(float(value))
    else:
        text = str(value).strip()
        if not text:
            return None
        if _DIGITS.match(text):
            return _from_epoch(float(text))
        if text.upper().endswith(" UTC"):
            text = text[:-4] + "+00:00"
        elif text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        text = _FRACTION.sub(_pad_fraction, text, count=1)
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
