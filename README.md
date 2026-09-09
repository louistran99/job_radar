# ATS job monitor

Poll public Greenhouse, Lever, Ashby, and Gem job boards for titles that match both a level phrase (engineering manager, director, TLM, …) and a domain phrase (mobile, iOS, Android, …) in the Bay Area, Los Angeles, Orange County, or remote. Diff against the last run and append to `output/report.md` (use `--replace-report` to overwrite).

No API keys. Email is not included yet.

```bash
python3 main.py --verbose
```

See [HOW_TO_USE.md](HOW_TO_USE.md) for local cron, GitHub Actions, and how to add companies.
