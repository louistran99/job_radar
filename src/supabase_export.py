"""Write companies and jobs to Supabase through PostgREST (service role)."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from src.bootstrap import REPO_ROOT
from src.models import Company

logger = logging.getLogger(__name__)

ENV_FILE = REPO_ROOT / ".env"
URL_VAR = "SUPABASE_URL"
KEY_VAR = "SUPABASE_SERVICE_ROLE_KEY"
JOBS_BATCH_SIZE = 500
READ_PAGE_SIZE = 1000  # Supabase caps a response at 1000 rows by default
TIMEOUT_SECONDS = 30


class ExportError(Exception):
    """Raised when the export cannot run or Supabase rejects a request."""


@dataclass(frozen=True)
class SupabaseSettings:
    url: str
    service_role_key: str


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.removeprefix("export ").strip()
        values[name] = value.strip().strip("'\"")
    return values


def load_settings(
    environ: Mapping[str, str] | None = None, env_file: Path = ENV_FILE
) -> SupabaseSettings:
    """Read the two Supabase settings from the environment, then from .env."""
    env = os.environ if environ is None else environ
    file_values = _read_env_file(env_file)
    url = env.get(URL_VAR) or file_values.get(URL_VAR) or ""
    key = env.get(KEY_VAR) or file_values.get(KEY_VAR) or ""
    missing = [
        name for name, value in ((URL_VAR, url), (KEY_VAR, key)) if not value
    ]
    if missing:
        raise ExportError(
            f"Missing {', '.join(missing)}. Set them in the environment or in {env_file}."
        )
    return SupabaseSettings(url=url.rstrip("/"), service_role_key=key)


class SupabaseStore:
    def __init__(self, session: requests.Session, settings: SupabaseSettings) -> None:
        self.session = session
        self.base_url = f"{settings.url}/rest/v1"
        self.headers = {
            "apikey": settings.service_role_key,
            "Authorization": f"Bearer {settings.service_role_key}",
        }

    def upsert_companies(self, companies: list[Company]) -> dict[tuple[str, str], str]:
        """Upsert on (ats, slug) and return each company's id keyed by (ats, slug)."""
        payload = [
            {
                "name": company.name,
                "ats": company.ats,
                "slug": company.slug,
                "enabled": company.enabled,
            }
            for company in companies
        ]
        rows = self._request(
            "POST",
            "companies",
            params={"on_conflict": "ats,slug"},
            prefer="resolution=merge-duplicates,return=representation",
            body=payload,
        )
        return {(row["ats"], row["slug"]): row["id"] for row in rows}

    def upsert_jobs(self, rows: list[dict[str, Any]]) -> None:
        """Upsert on (company_id, external_id) in batches."""
        for start in range(0, len(rows), JOBS_BATCH_SIZE):
            self._request(
                "POST",
                "jobs",
                params={"on_conflict": "company_id,external_id"},
                prefer="resolution=merge-duplicates,return=minimal",
                body=rows[start : start + JOBS_BATCH_SIZE],
            )

    def external_ids_for(self, company_id: str) -> set[str]:
        """Read back every external_id stored for one company."""
        external_ids: set[str] = set()
        offset = 0
        while True:
            rows = self._request(
                "GET",
                "jobs",
                params={
                    "company_id": f"eq.{company_id}",
                    "select": "external_id",
                    "order": "external_id",
                    "limit": READ_PAGE_SIZE,
                    "offset": offset,
                },
            )
            external_ids.update(row["external_id"] for row in rows)
            if len(rows) < READ_PAGE_SIZE:
                return external_ids
            offset += READ_PAGE_SIZE

    def _request(
        self,
        method: str,
        table: str,
        *,
        params: dict[str, Any],
        prefer: str | None = None,
        body: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        try:
            response = self.session.request(
                method,
                f"{self.base_url}/{table}",
                params=params,
                json=body,
                headers=headers,
                timeout=TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise ExportError(f"Supabase {method} {table} failed: {exc}") from exc
        if not response.ok:
            raise ExportError(
                f"Supabase {method} {table} returned {response.status_code}: "
                f"{response.text}"
            )
        return response.json() if response.content else []
