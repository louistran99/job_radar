"""Shared HTTP GET with 429 retries. No authentication."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
MAX_RETRIES = 5
USER_AGENT = "job-search-monitor/1.0"


class BoardNotFoundError(Exception):
    """Raised when an ATS board slug returns 404/410."""


class ATSClientError(Exception):
    """Raised when an ATS request fails after retries."""


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
    )
    return session


def get_json(
    session: requests.Session,
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=timeout)
        except requests.RequestException as exc:
            last_error = exc
            wait = 2**attempt
            logger.warning(
                "Request error for %s (%s), retrying in %ss", url, exc, wait
            )
            time.sleep(wait)
            continue

        if response.status_code in {404, 410}:
            raise BoardNotFoundError(
                f"Board not found: {url} ({response.status_code})"
            )

        if response.status_code == 429 or response.status_code >= 500:
            retry_after = response.headers.get("Retry-After", "")
            wait = int(retry_after) if retry_after.isdigit() else 2**attempt
            logger.warning(
                "Retryable status %s for %s, waiting %ss (attempt %s)",
                response.status_code,
                url,
                wait,
                attempt + 1,
            )
            time.sleep(wait)
            continue

        if not response.ok:
            raise ATSClientError(f"{url} returned {response.status_code}")

        try:
            return response.json()
        except ValueError as exc:
            raise ATSClientError(f"{url} returned invalid JSON") from exc

    if last_error is not None:
        raise ATSClientError(
            f"{url} failed after {max_retries} retries: {last_error}"
        ) from last_error
    raise ATSClientError(f"{url} failed after {max_retries} retries")
