from __future__ import annotations

import logging
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from src.clients.http import ATSClientError
from src.fetch import LiveFetcher
from src.models import Company

SMARTRECRUITERS_URL = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
WORKABLE_URL = "https://apply.workable.com/api/v1/widget/accounts/{slug}"


class _Response:
    def __init__(self, payload: Any) -> None:
        self.status_code = 200
        self.headers: dict[str, str] = {}
        self.ok = True
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class _PagingSession:
    """Serves `total` SmartRecruiters-shaped postings honouring limit/offset."""

    def __init__(self, total: int) -> None:
        self.total = total
        self.urls: list[str] = []

    def get(self, url: str, timeout: int = 30) -> _Response:
        self.urls.append(url)
        query = parse_qs(urlparse(url).query)
        limit = int(query.get("limit", ["100"])[0])
        offset = int(query.get("offset", ["0"])[0])
        content = [
            {
                "id": index,
                "name": f"Engineering Manager {index}",
                "location": {"fullLocation": "San Francisco, CA, United States"},
            }
            for index in range(offset, min(offset + limit, self.total))
        ]
        return _Response({"content": content, "totalFound": self.total})


class _SingleResponseSession:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.urls: list[str] = []

    def get(self, url: str, timeout: int = 30) -> _Response:
        self.urls.append(url)
        return _Response(self.payload)


def _company(ats: str, slug: str = "acme") -> Company:
    return Company(name="Acme", ats=ats, slug=slug)


def _smartrecruiters(**page: Any) -> dict[str, dict[str, Any]]:
    return {
        "smartrecruiters": {
            "enabled": True,
            "url": SMARTRECRUITERS_URL,
            "page": {"size": 100, **page},
        }
    }


def _offsets(urls: list[str]) -> list[int]:
    return [int(parse_qs(urlparse(url).query)["offset"][0]) for url in urls]


def test_paged_fetch_stops_on_short_page() -> None:
    session = _PagingSession(total=250)
    fetcher = LiveFetcher(session, _smartrecruiters())
    jobs = fetcher.fetch(_company("smartrecruiters"))
    assert len(jobs) == 250
    assert _offsets(session.urls) == [0, 100, 200]
    assert jobs[0].url.endswith("/acme/0")


def test_paged_fetch_requests_one_extra_page_on_exact_multiple() -> None:
    session = _PagingSession(total=200)
    fetcher = LiveFetcher(session, _smartrecruiters())
    jobs = fetcher.fetch(_company("smartrecruiters"))
    assert len(jobs) == 200
    assert _offsets(session.urls) == [0, 100, 200]


def test_paged_fetch_sends_limit_and_offset_params() -> None:
    session = _PagingSession(total=5)
    fetcher = LiveFetcher(session, _smartrecruiters())
    fetcher.fetch(_company("smartrecruiters"))
    query = parse_qs(urlparse(session.urls[0]).query)
    assert query == {"limit": ["100"], "offset": ["0"]}


def test_paged_fetch_stops_at_max_pages_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    session = _PagingSession(total=1000)
    fetcher = LiveFetcher(session, _smartrecruiters(max_pages=2))
    with caplog.at_level(logging.WARNING):
        jobs = fetcher.fetch(_company("smartrecruiters"))
    assert len(jobs) == 200
    assert _offsets(session.urls) == [0, 100]
    assert "stopped after 2 page(s)" in caplog.text


def test_paged_fetch_honours_custom_param_names() -> None:
    session = _PagingSession(total=1)
    sources = _smartrecruiters(limit_param="per_page", offset_param="start")
    LiveFetcher(session, sources).fetch(_company("smartrecruiters"))
    query = parse_qs(urlparse(session.urls[0]).query)
    assert query == {"per_page": ["100"], "start": ["0"]}


def test_unpaged_fetch_hits_the_board_once() -> None:
    payload = {
        "jobs": [
            {
                "title": "Engineering Manager, Mobile",
                "shortcode": "ABC123",
                "url": "https://apply.workable.com/j/ABC123",
                "telecommuting": True,
                "locations": [],
            }
        ]
    }
    session = _SingleResponseSession(payload)
    fetcher = LiveFetcher(session, {"workable": {"url": WORKABLE_URL}})
    jobs = fetcher.fetch(_company("workable", "huggingface"))
    assert len(jobs) == 1
    assert session.urls == [
        "https://apply.workable.com/api/v1/widget/accounts/huggingface"
    ]


def test_fetch_without_url_template_is_a_client_error() -> None:
    fetcher = LiveFetcher(_SingleResponseSession({}), {"workable": {"enabled": True}})
    with pytest.raises(ATSClientError, match="No URL template"):
        fetcher.fetch(_company("workable"))


def test_fetch_with_unknown_template_field_is_a_client_error() -> None:
    sources = {"workable": {"url": "https://example.com/{tenant}/jobs"}}
    fetcher = LiveFetcher(_SingleResponseSession({}), sources)
    with pytest.raises(ATSClientError, match="Bad URL template"):
        fetcher.fetch(_company("workable"))
