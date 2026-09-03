from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.config import load_jobs_config, resolve_config_path
from src.models import Company


def test_resolve_creates_local_copy_for_default_jobs_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import src.config as config

    default = tmp_path / "jobs.yaml"
    local = tmp_path / "jobs.local.yaml"
    default.write_text("companies:\n  - name: Acme\n    ats: greenhouse\n    slug: acme\n", encoding="utf-8")
    monkeypatch.setattr(config, "DEFAULT_JOBS_YAML", default)
    monkeypatch.setattr(config, "LOCAL_JOBS_YAML", local)

    resolved = config.resolve_config_path(default)
    assert resolved == local
    assert local.exists()
    assert "acme" in local.read_text(encoding="utf-8")


def test_resolve_uses_explicit_other_path_as_is(tmp_path: Path) -> None:
    other = tmp_path / "other.yaml"
    other.write_text("companies: []\n", encoding="utf-8")
    assert resolve_config_path(other) == other
    assert not (tmp_path / "jobs.local.yaml").exists()


def test_load_jobs_config_from_yaml(tmp_path: Path) -> None:
    path = tmp_path / "jobs.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "sources": {
                    "greenhouse": {
                        "enabled": True,
                        "url": "https://example.com/{slug}",
                    }
                },
                "title_match": {
                    "level": ["engineering manager"],
                    "domain": ["mobile"],
                },
                "locations": {"bay_area": ["san francisco"]},
                "companies": [
                    {
                        "name": "Acme",
                        "ats": "greenhouse",
                        "slug": "acme",
                        "enabled": True,
                    },
                    {
                        "name": "Off",
                        "ats": "greenhouse",
                        "slug": "off",
                        "enabled": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    loaded = load_jobs_config(path)
    assert [c.name for c in loaded.companies] == ["Acme", "Off"]
    assert loaded.companies[0] == Company(
        name="Acme", ats="greenhouse", slug="acme", enabled=True
    )
    assert loaded.level_patterns == ["engineering manager"]
    assert loaded.domain_patterns == ["mobile"]
    assert loaded.locations["bay_area"] == ["san francisco"]


def test_committed_jobs_yaml_loads() -> None:
    root = Path(__file__).resolve().parent.parent
    loaded = load_jobs_config(root / "config" / "jobs.yaml")
    assert loaded.level_patterns
    assert loaded.domain_patterns
    assert loaded.locations["bay_area"]
    assert loaded.locations["los_angeles"]
    assert loaded.locations["orange_county"]
    assert loaded.locations["remote"]
    assert len(loaded.companies) >= 25
    assert "greenhouse" in loaded.sources
    assert "lever" in loaded.sources
    assert "ashby" in loaded.sources
    assert "gem" in loaded.sources
    assert "{slug}" in loaded.sources["greenhouse"]["url"]
    assert "{slug}" in loaded.sources["gem"]["url"]
