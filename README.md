# ATS job monitor

Poll public Greenhouse, Lever, Ashby, and Gem job boards for titles that match both a level phrase (engineering manager, director, TLM, …) and a domain phrase (mobile, iOS, Android, …) in the Bay Area, Los Angeles, Orange County, or remote. Diff against the last run and prepend to `output/report.md` (use `--replace-report` to overwrite).

No API keys. Email is not included yet.

```bash
python3 main.py --verbose
python3 main.py --small-set smallset.json --verbose
```

## Config

Search filters live in [`config/jobs.json`](config/jobs.json). The first local run copies that file to gitignored `config/jobs.local.json`, and later `python3 main.py` uses the local copy. Edit `jobs.local.json` for personal title/location tweaks; edit `jobs.json` only when changing the shared defaults.

Company boards live in [`config/companies.json`](config/companies.json). ATS URL templates live in [`config/ats.json`](config/ats.json). Every company whose ATS is implemented and enabled in `ats.json` is fetched. For a short test run, pass `--small-set smallset.json` (see [`config/smallset.json`](config/smallset.json)).

### Level and domain

A title must match at least one `title_match.level` phrase **and** at least one `title_match.domain` phrase (substring match on the normalized title). Adding `staff` or `engineer` to level, or dropping domain phrases, changes what gets reported. A “Director of Engineering” with no mobile / iOS / Android (or other domain) word is skipped.

```json
{
  "title_match": {
    "level": ["manager", "head of", "director"],
    "domain": ["mobile", "ios", "android"]
  }
}
```

### Companies

Each entry is `{name, ats, slug}`. Workday rows use `{name, ats, workday}` instead of `slug`. Supported fetch `ats` values: `greenhouse`, `lever`, `ashby`, `gem`. Disable a whole ATS with `"enabled": false` in [`config/ats.json`](config/ats.json). Add a board by appending an object and setting the careers-site slug. Bad slugs are skipped with a warning.

```json
{ "name": "Stripe", "ats": "greenhouse", "slug": "stripe" }
```

See [HOW_TO_USE.md](HOW_TO_USE.md) for locations, local cron, and GitHub Actions.
