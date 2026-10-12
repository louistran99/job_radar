from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.config import DEFAULT_JOBS_JSON, JobsConfig, load_app_config
from src.export import (
    ExportResult,
    configure_logging,
    job_row,
    run_export,
    summary,
)
from src.models import Company, Job
from src.supabase_export import (
    ExportError,
    SupabaseSettings,
    SupabaseStore,
    load_settings,
)
from tests.fakes import FakeFetcher, FakeStore

SMALLSET = Path(__file__).resolve().parent.parent / "config" / "smallset.json"


def _job(slug: str, job_id: str, title: str = "Engineer", **extra: object) -> Job:
    return Job(
        ats="greenhouse",
        slug=slug,
        job_id=job_id,
        company=slug.title(),
        title=title,
        url=f"https://example.com/{slug}/{job_id}",
        locations=["Remote"],
        **extra,
    )


def _config(*companies: Company) -> JobsConfig:
    return JobsConfig(
        sources={"greenhouse": {"enabled": True, "url": "https://x/{slug}"}},
        companies=list(companies),
        delay_seconds=0,
    )


def _acme() -> Company:
    return Company(name="Acme", ats="greenhouse", slug="acme")


def test_job_row_maps_job_fields() -> None:
    posted = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    job = _job("acme", "7", workplace_type="hybrid", posted_at=posted)
    assert job_row(job, "cid") == {
        "company_id": "cid",
        "external_id": "7",
        "title": "Engineer",
        "url": "https://example.com/acme/7",
        "locations": ["Remote"],
        "workplace_type": "hybrid",
        "posted_at": "2026-09-01T12:00:00+00:00",
    }


def test_job_row_nulls_unknown_workplace_type_and_missing_posted_at() -> None:
    row = job_row(_job("acme", "7", workplace_type="flexible"), "cid")
    assert row["workplace_type"] is None
    assert row["posted_at"] is None


def test_every_company_in_the_file_gets_rows() -> None:
    config = load_app_config(DEFAULT_JOBS_JSON, companies_path=SMALLSET)
    names = [entry["name"] for entry in json.loads(SMALLSET.read_text())]
    jobs = {
        (c.ats, c.slug): [
            Job(
                ats=c.ats,
                slug=c.slug,
                job_id="1",
                company=c.name,
                title="Engineer",
                url="https://example.com/1",
            )
        ]
        for c in config.companies
    }
    store = FakeStore()
    result = run_export(config, FakeFetcher(jobs=jobs), store, delay_seconds=0)
    assert sorted(result.exported) == sorted(names)
    assert len(store.jobs) == len(names)
    assert result.ok


def test_skips_missing_and_failing_boards_but_exports_the_rest() -> None:
    boards = [
        Company(name="Acme", ats="greenhouse", slug="acme"),
        Company(name="Gone", ats="greenhouse", slug="gone"),
        Company(name="Broken", ats="greenhouse", slug="broken"),
    ]
    fetcher = FakeFetcher(
        jobs={("greenhouse", "acme"): [_job("acme", "1")]},
        missing={("greenhouse", "gone")},
        errors={("greenhouse", "broken"): "boom"},
    )
    store = FakeStore()
    result = run_export(_config(*boards), fetcher, store, delay_seconds=0)
    assert result.exported == {"Acme": 1}
    assert result.skipped == ["Gone", "Broken"]
    assert result.ok


def test_board_with_no_jobs_is_reported_not_failed() -> None:
    result = run_export(_config(_acme()), FakeFetcher(), FakeStore(), delay_seconds=0)
    assert result.empty == ["Acme"]
    assert result.ok


def test_no_enabled_companies_is_an_error() -> None:
    with pytest.raises(ExportError):
        run_export(_config(), FakeFetcher(), FakeStore(), delay_seconds=0)


def test_duplicate_job_id_is_written_once_and_last_wins() -> None:
    fetcher = FakeFetcher(
        jobs={
            ("greenhouse", "acme"): [
                _job("acme", "1", "Old title"),
                _job("acme", "1", "New title"),
            ]
        }
    )
    store = FakeStore()
    result = run_export(_config(_acme()), fetcher, store, delay_seconds=0)
    assert result.exported == {"Acme": 1}
    assert [row["title"] for row in store.jobs.values()] == ["New title"]


def test_same_company_listed_twice_is_fetched_once() -> None:
    fetcher = FakeFetcher(jobs={("greenhouse", "acme"): [_job("acme", "1")]})
    run_export(_config(_acme(), _acme()), fetcher, FakeStore(), delay_seconds=0)
    assert len(fetcher.calls) == 1


def test_verify_fails_when_read_back_is_missing_rows() -> None:
    fetcher = FakeFetcher(
        jobs={("greenhouse", "acme"): [_job("acme", "1"), _job("acme", "2")]}
    )
    store = FakeStore(lose={"2"})
    result = run_export(_config(_acme()), fetcher, store, delay_seconds=0)
    assert result.missing == {"Acme": 1}
    assert not result.ok
    assert "VERIFY FAILED: Acme is missing 1 row(s)" in summary(result)


def test_summary_lists_skipped_and_empty_boards() -> None:
    text = summary(ExportResult(exported={"A": 2}, empty=["B"], skipped=["C"]))
    assert "Exported 2 job(s) from 1 company(ies)." in text
    assert "No jobs returned: B" in text
    assert "Skipped (404 or fetch error): C" in text
    assert "Verified" in text


@pytest.fixture
def restore_root_logger() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    root.handlers, root.level = handlers, level


@pytest.mark.usefixtures("restore_root_logger")
def test_enable_logging_writes_each_step_to_the_log_file(tmp_path: Path) -> None:
    log_path = tmp_path / "out" / "fetchjobs.log"
    configure_logging(True, log_path)
    fetcher = FakeFetcher(jobs={("greenhouse", "acme"): [_job("acme", "1", "Staff")]})
    run_export(_config(_acme()), fetcher, FakeStore(), delay_seconds=0)
    for handler in logging.getLogger().handlers:
        handler.flush()
    text = log_path.read_text(encoding="utf-8")
    assert "Fetching jobs for Acme" in text
    assert "Fetched 1 job(s) for Acme" in text
    assert "Mapped Acme job 1 to a jobs row: Staff" in text
    assert "Exported 1 job(s) for Acme to the jobs table" in text
    assert "Verified Acme" in text


@pytest.mark.usefixtures("restore_root_logger")
def test_logging_off_writes_no_log_file(tmp_path: Path) -> None:
    log_path = tmp_path / "fetchjobs.log"
    configure_logging(False, log_path)
    assert not log_path.exists()


def test_load_settings_prefers_environment_over_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\nSUPABASE_URL='https://file.example/'\n"
        "export SUPABASE_SERVICE_ROLE_KEY=file-key\n",
        encoding="utf-8",
    )
    settings = load_settings({"SUPABASE_URL": "https://env.example"}, env_file)
    assert settings == SupabaseSettings("https://env.example", "file-key")


def test_load_settings_names_what_is_missing(tmp_path: Path) -> None:
    with pytest.raises(ExportError, match="SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY"):
        load_settings({}, tmp_path / ".env")


class _Response:
    def __init__(self, payload: list[dict], ok: bool = True) -> None:
        self.payload, self.ok = payload, ok
        self.status_code = 200 if ok else 400
        self.text = "bad request"
        self.content = b"x"

    def json(self) -> list[dict]:
        return self.payload


class _Session:
    def __init__(self, *responses: _Response) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def request(self, method: str, url: str, **kwargs: object) -> _Response:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)


def _store(session: _Session) -> SupabaseStore:
    return SupabaseStore(session, SupabaseSettings("https://p.supabase.co", "key"))  # type: ignore[arg-type]


def test_store_upserts_companies_on_ats_and_slug() -> None:
    session = _Session(_Response([{"id": "u1", "ats": "greenhouse", "slug": "acme"}]))
    ids = _store(session).upsert_companies([_acme()])
    call = session.calls[0]
    assert ids == {("greenhouse", "acme"): "u1"}
    assert call["url"] == "https://p.supabase.co/rest/v1/companies"
    assert call["params"] == {"on_conflict": "ats,slug"}
    assert call["headers"]["Authorization"] == "Bearer key"
    assert "merge-duplicates" in call["headers"]["Prefer"]


def test_store_reads_external_ids_for_one_company() -> None:
    session = _Session(_Response([{"external_id": "1"}, {"external_id": "2"}]))
    assert _store(session).external_ids_for("u1") == {"1", "2"}
    assert session.calls[0]["params"]["company_id"] == "eq.u1"


def test_store_raises_with_supabase_error_text() -> None:
    session = _Session(_Response([], ok=False))
    with pytest.raises(ExportError, match="400: bad request"):
        _store(session).upsert_jobs([{"company_id": "u1", "external_id": "1"}])
