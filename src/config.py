"""JSON config loading and local jobs overlay."""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.models import Company

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DEFAULT_JOBS_JSON = CONFIG_DIR / "jobs.json"
LOCAL_JOBS_JSON = CONFIG_DIR / "jobs.local.json"
DEFAULT_COMPANIES_JSON = CONFIG_DIR / "companies.json"
DEFAULT_ATS_JSON = CONFIG_DIR / "ats.json"

IMPLEMENTED_ATS = frozenset({"greenhouse", "lever", "ashby", "gem"})
_COMPANY_META_KEYS = frozenset({"name", "ats", "slug", "platform", "enabled"})


@dataclass
class JobsConfig:
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    companies: list[Company] = field(default_factory=list)
    level_patterns: list[str] = field(default_factory=list)
    domain_patterns: list[str] = field(default_factory=list)
    locations: dict[str, list[str]] = field(default_factory=dict)
    delay_seconds: float = 0.35


def resolve_jobs_path(config_path: Path | None) -> Path:
    """Prefer jobs.local.json when using the default committed jobs.json.

    First local run copies jobs.json → jobs.local.json if the local file
    is missing. An explicit --config pointing at any other file is used as-is.
    """
    if config_path is None:
        config_path = DEFAULT_JOBS_JSON

    resolved = config_path.expanduser().resolve()
    if resolved != DEFAULT_JOBS_JSON.resolve():
        return config_path

    if not LOCAL_JOBS_JSON.exists() and DEFAULT_JOBS_JSON.exists():
        shutil.copyfile(DEFAULT_JOBS_JSON, LOCAL_JOBS_JSON)
        logger.info(
            "Created %s from %s — edit the local copy; it is gitignored.",
            LOCAL_JOBS_JSON,
            DEFAULT_JOBS_JSON,
        )

    if LOCAL_JOBS_JSON.exists():
        return LOCAL_JOBS_JSON
    return config_path


def resolve_companies_path(companies_path: Path | None) -> Path:
    """Use PATH if it exists, otherwise look under config/ for a relative name.

    None falls back to config/companies.json. Missing files raise SystemExit.
    """
    if companies_path is None:
        return DEFAULT_COMPANIES_JSON

    if companies_path.exists():
        return companies_path

    if not companies_path.is_absolute():
        under_config = CONFIG_DIR / companies_path
        if under_config.exists():
            return under_config

    raise SystemExit(f"Companies file not found: {companies_path}")


def _format_json_error(config_path: Path, exc: json.JSONDecodeError) -> str:
    return (
        f"Invalid JSON in {config_path}\n"
        f"  {exc.msg} at line {exc.lineno}, column {exc.colno}"
    )


def _load_json(config_path: Path) -> Any:
    try:
        with config_path.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise SystemExit(_format_json_error(config_path, exc)) from None
    except OSError as exc:
        raise SystemExit(f"Could not read {config_path}: {exc}") from None


def _phrase_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(p).strip() for p in values if str(p).strip()]


def _parse_jobs_file(data: Any, config_path: Path) -> tuple[list[str], list[str], dict[str, list[str]], float]:
    if not isinstance(data, dict):
        raise SystemExit(f"Config {config_path} must be a JSON object.")

    raw_title_match = data.get("title_match") or {}
    if not isinstance(raw_title_match, dict):
        raw_title_match = {}
    level_patterns = _phrase_list(raw_title_match.get("level"))
    domain_patterns = _phrase_list(raw_title_match.get("domain"))

    raw_locations = data.get("locations") or {}
    locations: dict[str, list[str]] = {}
    if isinstance(raw_locations, dict):
        for key, values in raw_locations.items():
            if isinstance(values, list):
                locations[str(key)] = _phrase_list(values)

    settings = data.get("settings") or {}
    delay = 0.35
    if isinstance(settings, dict) and settings.get("delay_seconds") is not None:
        delay = float(settings["delay_seconds"])

    return level_patterns, domain_patterns, locations, delay


def _parse_companies(data: Any, config_path: Path) -> list[Company]:
    if not isinstance(data, list):
        raise SystemExit(f"Config {config_path} must be a JSON array.")

    companies: list[Company] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        ats = str(entry.get("ats") or entry.get("platform") or "").strip().lower()
        slug = str(entry.get("slug") or "").strip()
        params = {
            key: value
            for key, value in entry.items()
            if key not in _COMPANY_META_KEYS
        }
        if not name or not ats:
            logger.warning("Skipping incomplete company entry: %s", entry)
            continue
        if not slug and ats != "workday" and "workday" not in params:
            logger.warning("Skipping incomplete company entry: %s", entry)
            continue
        companies.append(Company(name=name, ats=ats, slug=slug, params=params))
    return companies


def _parse_ats(data: Any, config_path: Path) -> dict[str, dict[str, Any]]:
    if not isinstance(data, dict):
        raise SystemExit(f"Config {config_path} must be a JSON object.")
    sources: dict[str, dict[str, Any]] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            sources[str(key)] = value
    return sources


def load_app_config(
    jobs_path: Path,
    companies_path: Path | None = None,
    ats_path: Path | None = None,
) -> JobsConfig:
    companies_path = companies_path or DEFAULT_COMPANIES_JSON
    ats_path = ats_path or DEFAULT_ATS_JSON

    level_patterns, domain_patterns, locations, delay = _parse_jobs_file(
        _load_json(jobs_path), jobs_path
    )
    return JobsConfig(
        sources=_parse_ats(_load_json(ats_path), ats_path),
        companies=_parse_companies(_load_json(companies_path), companies_path),
        level_patterns=level_patterns,
        domain_patterns=domain_patterns,
        locations=locations,
        delay_seconds=delay,
    )


def enabled_companies(config: JobsConfig) -> list[Company]:
    enabled: list[Company] = []
    for company in config.companies:
        source = config.sources.get(company.ats) or {}
        if source.get("enabled") is False:
            logger.info(
                "Skipping %s: ATS %s is disabled in sources",
                company.name,
                company.ats,
            )
            continue
        if company.ats not in IMPLEMENTED_ATS:
            logger.warning(
                "Skipping %s: ATS %s is not implemented yet",
                company.name,
                company.ats,
            )
            continue
        template = source.get("url")
        if not template:
            logger.warning(
                "Skipping %s: no URL template for ATS %s",
                company.name,
                company.ats,
            )
            continue
        if "{slug}" in str(template) and not company.slug:
            logger.warning(
                "Skipping %s: no slug for ATS %s",
                company.name,
                company.ats,
            )
            continue
        enabled.append(company)
    return enabled
