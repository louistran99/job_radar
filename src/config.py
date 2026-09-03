"""YAML config loading and local override."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.models import Company

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DEFAULT_JOBS_YAML = CONFIG_DIR / "jobs.yaml"
LOCAL_JOBS_YAML = CONFIG_DIR / "jobs.local.yaml"

IMPLEMENTED_ATS = frozenset({"greenhouse", "lever", "ashby", "gem"})


@dataclass
class JobsConfig:
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    companies: list[Company] = field(default_factory=list)
    title_patterns: list[str] = field(default_factory=list)
    locations: dict[str, list[str]] = field(default_factory=dict)
    delay_seconds: float = 0.35


def resolve_config_path(config_path: Path | None) -> Path:
    """Prefer jobs.local.yaml when using the default committed jobs.yaml.

    First local run copies jobs.yaml → jobs.local.yaml if the local file
    is missing. An explicit --config pointing at any other file is used as-is.
    """
    if config_path is None:
        config_path = DEFAULT_JOBS_YAML

    resolved = config_path.expanduser().resolve()
    if resolved != DEFAULT_JOBS_YAML.resolve():
        return config_path

    if not LOCAL_JOBS_YAML.exists() and DEFAULT_JOBS_YAML.exists():
        shutil.copyfile(DEFAULT_JOBS_YAML, LOCAL_JOBS_YAML)
        logger.info(
            "Created %s from %s — edit the local copy; it is gitignored.",
            LOCAL_JOBS_YAML,
            DEFAULT_JOBS_YAML,
        )

    if LOCAL_JOBS_YAML.exists():
        return LOCAL_JOBS_YAML
    return config_path


def load_jobs_config(config_path: Path) -> JobsConfig:
    with config_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"Config {config_path} must be a YAML mapping.")

    sources = data.get("sources") or {}
    if not isinstance(sources, dict):
        sources = {}

    companies: list[Company] = []
    for entry in data.get("companies") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        ats = str(entry.get("ats") or "").strip().lower()
        slug = str(entry.get("slug") or "").strip()
        if not name or not ats or not slug:
            logger.warning("Skipping incomplete company entry: %s", entry)
            continue
        companies.append(
            Company(
                name=name,
                ats=ats,
                slug=slug,
                enabled=bool(entry.get("enabled", True)),
            )
        )

    title_patterns = [
        str(p).strip()
        for p in (data.get("title_patterns") or [])
        if str(p).strip()
    ]

    raw_locations = data.get("locations") or {}
    locations: dict[str, list[str]] = {}
    if isinstance(raw_locations, dict):
        for key, values in raw_locations.items():
            if isinstance(values, list):
                locations[str(key)] = [str(v).strip() for v in values if str(v).strip()]

    settings = data.get("settings") or {}
    delay = 0.35
    if isinstance(settings, dict) and settings.get("delay_seconds") is not None:
        delay = float(settings["delay_seconds"])

    return JobsConfig(
        sources=sources,
        companies=companies,
        title_patterns=title_patterns,
        locations=locations,
        delay_seconds=delay,
    )


def enabled_companies(config: JobsConfig) -> list[Company]:
    enabled: list[Company] = []
    for company in config.companies:
        if not company.enabled:
            continue
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
        if not source.get("url"):
            logger.warning(
                "Skipping %s: no URL template for ATS %s",
                company.name,
                company.ats,
            )
            continue
        enabled.append(company)
    return enabled
