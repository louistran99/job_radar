# ATS job monitor

Poll public Greenhouse, Lever, Ashby, and Gem job boards for titles that match both a level phrase (engineering manager, director, TLM, …) and a domain phrase (mobile, iOS, Android, …) in the Bay Area, Los Angeles, Orange County, or remote. Diff against the last run and append to `output/report.md` (use `--replace-report` to overwrite).

No API keys. Email is not included yet.

```bash
python3 main.py --verbose
```

## Config

Committed defaults live in [`config/jobs.yaml`](config/jobs.yaml). The first local run copies that file to gitignored `config/jobs.local.yaml`, and later `python3 main.py` uses the local copy. Edit `jobs.local.yaml` for personal tweaks; edit `jobs.yaml` only when changing the shared defaults.

### Level and domain

A title must match at least one `title_match.level` phrase **and** at least one `title_match.domain` phrase (substring match on the normalized title). Adding `staff` or `engineer` to level, or dropping domain phrases, changes what gets reported. A “Director of Engineering” with no mobile / iOS / Android (or other domain) word is skipped.

```yaml
title_match:
  level:
    - manager
    - head of
    - director
  domain:
    - mobile
    - ios
    - android
```

### Companies

Each entry is `{name, ats, slug, enabled}`. Supported `ats` values: `greenhouse`, `lever`, `ashby`, `gem`. Disable a board with `enabled: false`. Add one by copying an existing entry and setting the careers-site slug. Bad slugs are skipped with a warning.

```yaml
companies:
  - name: Stripe
    ats: greenhouse
    slug: stripe
    enabled: true
```

See [HOW_TO_USE.md](HOW_TO_USE.md) for locations, local cron, and GitHub Actions.
