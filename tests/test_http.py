from __future__ import annotations

import pytest

from src.clients.http import ATSClientError, BoardNotFoundError, get_json


class _Response:
    def __init__(self, status_code: int, payload: object | None = None, headers: dict | None = None) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self._payload = payload
        self.ok = 200 <= status_code < 400

    def json(self) -> object:
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class _Session:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.urls: list[str] = []

    def get(self, url: str, timeout: int = 30) -> _Response:
        self.urls.append(url)
        return self.response


def test_get_json_404_is_board_not_found() -> None:
    session = _Session(_Response(404))
    with pytest.raises(BoardNotFoundError):
        get_json(session, "https://example.com/boards/missing")  # type: ignore[arg-type]


def test_get_json_ok_returns_payload() -> None:
    session = _Session(_Response(200, {"jobs": []}))
    assert get_json(session, "https://example.com/boards/acme") == {"jobs": []}  # type: ignore[arg-type]


def test_get_json_400_is_client_error() -> None:
    session = _Session(_Response(400, {"error": "bad"}))
    with pytest.raises(ATSClientError):
        get_json(session, "https://example.com/boards/acme")  # type: ignore[arg-type]
