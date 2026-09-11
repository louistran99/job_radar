# How to Use — ATS job monitor

Operational guide for local setup, crontab, and GitHub Actions.

## Prerequisites

- Python 3.10 or newer
- Git

A GitHub remote is only required for the daily Action (Phase 2). Local CLI and cron work without it.

## First-time local setup

From this repo root:

```bash
python3 main.py --verbose
```

That one command creates `.venv`, installs dependencies, then fetches. Later runs reuse the venv and skip install when packages are already present. Progress prints as `1 of 5 (…)` through `5 of 5 (…)`.

In Cursor or VS Code, select the Python interpreter at `.venv/bin/python`.

## Config

Three committed JSON files:

| File | Purpose |
|------|---------|
| [`config/jobs.json`](config/jobs.json) | Title match axes (level AND domain), location keywords, fetch delay |
| [`config/companies.json`](config/companies.json) | Company catalog (`name`, `ats`, `slug`, or Workday params) |
| [`config/smallset.json`](config/smallset.json) | 15-company subset for local test runs (`--small-set`) |
| [`config/ats.json`](config/ats.json) | ATS URL templates and enabled flags |

The first run that uses the default path copies `jobs.json` to **gitignored** `config/jobs.local.json`. Edit the local copy to change level/domain phrases or locations without dirtying git. Add or change companies in `companies.json`.

```bash
python3 main.py --verbose         # setup + fetch (creates .venv on first run)
python3 main.py --validate-only   # probe slugs; 404s are skipped with a warning
python3 main.py --replace-report  # overwrite report.md instead of prepending
python3 main.py --config /path/to/other.json
python3 main.py --small-set smallset.json --verbose
```

Bad slugs are skipped, not a hard fail. Disable an ATS in `ats.json` with `"enabled": false`. Every company whose ATS is implemented and enabled is fetched unless `--small-set` points at a subset file (relative names also resolve under `config/`).

Gem boards use the path segment from `https://jobs.gem.com/{slug}`:

```json
{ "name": "Gem", "ats": "gem", "slug": "gem" }
```

Probe a board (same headers as the monitor). Unknown slugs return 404 and are skipped:

```bash
curl -i 'https://api.gem.com/job_board/v0/gem/job_posts/' \
  -H 'Accept: application/json' \
  -H 'User-Agent: job-search-monitor/1.0'
```

Disabled stubs for Workday, SmartRecruiters, Workable, Recruitee, Personio, and BambooHR live in `ats.json` (see [ATS API reference](https://conorscode.github.io/ats-api-reference/)).

## Output

Gitignored `output/`:

| File | Purpose |
|------|---------|
| `snapshot.json` | Matched jobs from this run (identity `{ats}:{slug}:{job_id}`) |
| `report.md` | New / Removed / Still open (first run is a baseline, not “all new”). Each run prepends; `--replace-report` overwrites. |

The report markdown is the future email body.

## Tests

```bash
pytest
```

Tests use in-memory fakes and do not call the network.

## macOS cron (06:00 Pacific)

`crontab -e`. macOS cron uses the system timezone; set the Mac to Pacific or use `CRON_TZ` where supported. Replace `/path/to/this/repo` with the absolute path to your clone:

```
CRON_TZ=America/Los_Angeles
0 6 * * * cd /path/to/this/repo && mkdir -p output && .venv/bin/python main.py >> output/cron.log 2>&1
```

## GitHub Action (after local works)

The workflow [`.github/workflows/fetch-jobs.yml`](.github/workflows/fetch-jobs.yml) lives on `main` at `github.com:louistran99/job_radar`. The daily schedule only runs from the default branch.

- Cron: `0 14 * * *` UTC ≈ 06:00 PST / 07:00 PDT
- Also runnable via **Actions → Fetch jobs → Run workflow**
- No secrets for fetching
- Previous `jobs-snapshot` artifact is downloaded when present (first CI run is a baseline)
- `output/` is uploaded as `jobs-snapshot` even if the job fails

After the Action is proven, SMTP can be added via `.env` / GitHub Secrets. Email is not in this version.
