from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config import (
    DEFAULT_COMPANIES_JSON,
    enabled_companies,
    load_app_config,
    resolve_companies_path,
    resolve_jobs_path,
)
from src.models import Company


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_resolve_creates_local_copy_for_default_jobs_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import src.config as config

    default = tmp_path / "jobs.json"
    local = tmp_path / "jobs.local.json"
    default.write_text('{"title_match": {"level": ["manager"]}}', encoding="utf-8")
    monkeypatch.setattr(config, "DEFAULT_JOBS_JSON", default)
    monkeypatch.setattr(config, "LOCAL_JOBS_JSON", local)

    resolved = config.resolve_jobs_path(default)
    assert resolved == local
    assert local.exists()
    assert "manager" in local.read_text(encoding="utf-8")


def test_resolve_uses_explicit_other_path_as_is(tmp_path: Path) -> None:
    other = tmp_path / "other.json"
    other.write_text("{}", encoding="utf-8")
    assert resolve_jobs_path(other) == other
    assert not (tmp_path / "jobs.local.json").exists()


def test_load_app_config_from_json_files(tmp_path: Path) -> None:
    jobs_path = _write_json(
        tmp_path / "jobs.json",
        {
            "settings": {"delay_seconds": 0.5},
            "title_match": {
                "level": ["engineering manager"],
                "domain": ["mobile"],
            },
            "locations": {"bay_area": ["san francisco"]},
        },
    )
    companies_path = _write_json(
        tmp_path / "companies.json",
        [
            {"name": "Acme", "ats": "greenhouse", "slug": "acme"},
            {
                "name": "Intel",
                "ats": "workday",
                "workday": {"tenant": "intel", "site": "External", "shard": "wd1"},
            },
        ],
    )
    ats_path = _write_json(
        tmp_path / "ats.json",
        {
            "greenhouse": {
                "enabled": True,
                "url": "https://example.com/{slug}",
            },
            "workday": {"enabled": False, "url": "https://example.com/{tenant}"},
        },
    )

    loaded = load_app_config(jobs_path, companies_path, ats_path)
    assert [c.name for c in loaded.companies] == ["Acme", "Intel"]
    assert loaded.companies[0] == Company(
        name="Acme", ats="greenhouse", slug="acme"
    )
    assert loaded.companies[1].params["workday"]["tenant"] == "intel"
    assert loaded.level_patterns == ["engineering manager"]
    assert loaded.domain_patterns == ["mobile"]
    assert loaded.locations["bay_area"] == ["san francisco"]
    assert loaded.delay_seconds == 0.5
    assert loaded.sources["greenhouse"]["url"] == "https://example.com/{slug}"

    fetchable = enabled_companies(loaded)
    assert [c.name for c in fetchable] == ["Acme"]


def test_load_app_config_invalid_json(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs.json"
    jobs_path.write_text("{", encoding="utf-8")
    with pytest.raises(SystemExit, match="Invalid JSON"):
        load_app_config(jobs_path, jobs_path, jobs_path)


def test_committed_json_configs_load() -> None:
    root = Path(__file__).resolve().parent.parent
    loaded = load_app_config(
        root / "config" / "jobs.json",
        root / "config" / "companies.json",
        root / "config" / "ats.json",
    )
    assert loaded.level_patterns
    assert loaded.domain_patterns
    assert loaded.locations["bay_area"]
    assert loaded.locations["los_angeles"]
    assert loaded.locations["orange_county"]
    assert loaded.locations["remote"]
    assert len(loaded.companies) >= 100
    names = {c.name for c in loaded.companies}
    assert {"Block", "Plaid", "Thumbtack", "Gem", "Quo", "Vercel", "Mercury"} <= names
    vercel = next(c for c in loaded.companies if c.name == "Vercel")
    mercury = next(c for c in loaded.companies if c.name == "Mercury")
    assert vercel.ats == "ashby"
    assert mercury.ats == "ashby"
    assert "greenhouse" in loaded.sources
    assert "lever" in loaded.sources
    assert "ashby" in loaded.sources
    assert "gem" in loaded.sources
    assert "{slug}" in loaded.sources["greenhouse"]["url"]
    assert "{slug}" in loaded.sources["gem"]["url"]
    fetchable = enabled_companies(loaded)
    assert len(fetchable) >= 100
    assert all(c.ats in {"greenhouse", "lever", "ashby", "gem"} for c in fetchable)
    assert all(c.slug for c in fetchable)


def test_resolve_companies_path_none_is_default() -> None:
    assert resolve_companies_path(None) == DEFAULT_COMPANIES_JSON


def test_resolve_companies_path_uses_existing_path(tmp_path: Path) -> None:
    path = tmp_path / "subset.json"
    path.write_text("[]", encoding="utf-8")
    assert resolve_companies_path(path) == path


def test_resolve_companies_path_looks_under_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import src.config as config

    under_config = tmp_path / "smallset.json"
    under_config.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    assert config.resolve_companies_path(Path("smallset.json")) == under_config


def test_resolve_companies_path_missing_raises(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    with pytest.raises(SystemExit, match="Companies file not found"):
        resolve_companies_path(missing)


def test_committed_smallset_json_loads() -> None:
    root = Path(__file__).resolve().parent.parent
    loaded = load_app_config(
        root / "config" / "jobs.json",
        root / "config" / "smallset.json",
        root / "config" / "ats.json",
    )
    names = [c.name for c in loaded.companies]
    assert len(names) == 15
    assert names == [
        "Stripe",
        "Airbnb",
        "Discord",
        "Figma",
        "Anthropic",
        "Notion",
        "Plaid",
        "Vercel",
        "OpenAI",
        "Linear",
        "Thumbtack",
        "Palantir",
        "Spotify",
        "Gem",
        "Quo",
    ]
    assert {c.ats for c in loaded.companies} == {"greenhouse", "ashby", "lever", "gem"}
    fetchable = enabled_companies(loaded)
    assert len(fetchable) == 15
