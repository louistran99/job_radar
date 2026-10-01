# ATS response shapes

What each public job board API returns and how `src/clients/*.py` maps it onto
`Job` (see [`src/models.py`](../src/models.py)). All endpoints are unauthenticated.
Payload samples were captured on 2026-09-30; only the fields the adapters read
are listed.

Every adapter exposes the same two functions:

- `extract_jobs(payload)` — pull the raw posting records out of the envelope.
- `normalize(raw, company)` — build one `Job`, or `None` to drop the record.

Each adapter drops records with no id or a blank title.

## Summary

| ATS | Records at | Job id | Title | Job URL | Paged |
|-----|-----------|--------|-------|---------|-------|
| Greenhouse | `jobs[]` | `id` | `title` | `absolute_url` | no |
| Lever | bare array | `id` | `text` | `hostedUrl` | no |
| Ashby | `jobs[]` | `id` | `title` | `jobUrl` | no |
| Gem | bare array | `id` | `title` | `absolute_url` | no |
| SmartRecruiters | `content[]` | `id` | `name` | built | yes, `limit`/`offset` |
| Workable | `jobs[]` | `shortcode` | `title` | `url` | no |
| Recruitee | `offers[]` | `id` | `title` | `careers_url` | no |
| Personio | bare array | `id` | `name` | built | no |
| BambooHR | `result[]` | `id` | `jobOpeningName` | built | no |

Four boards return no public job URL, so the adapter builds one. Each pattern
below was confirmed to return HTTP 200.

| ATS | Constructed URL |
|-----|-----------------|
| SmartRecruiters | `https://jobs.smartrecruiters.com/{slug}/{id}` |
| Personio | `https://{slug}.jobs.personio.de/job/{id}` |
| BambooHR | `https://{slug}.bamboohr.com/careers/{id}` |

## SmartRecruiters

`GET https://api.smartrecruiters.com/v1/companies/{slug}/postings`

The slug is the company identifier and is case sensitive (`BoschGroup`, not
`boschgroup`). An unknown slug returns HTTP 200 with `totalFound: 0` rather than
a 404, so a typo looks like an empty board instead of a skip.

```json
{
  "offset": 0,
  "limit": 100,
  "totalFound": 167,
  "content": [
    {
      "id": "744000152827243",
      "name": "Lead Hardware Engineer",
      "refNumber": "REF297343B",
      "releasedDate": "2026-10-01T04:54:45.327Z",
      "location": {
        "city": "Lincolnshire",
        "region": "IL",
        "country": "us",
        "fullLocation": "Lincolnshire, IL, United States",
        "remote": false,
        "hybrid": true
      }
    }
  ]
}
```

- **Pagination is required.** `limit` is capped at 100 server-side however large
  a value is sent, and large boards are well past that (Bosch Group returns
  4,835 postings). `LiveFetcher` walks `offset` in `limit`-sized steps; see
  [Pagination](#pagination).
- `location.fullLocation` keeps empty segments when a field is unset, as in
  `"bangalore, , India"`. The adapter strips those to `"bangalore, India"` and
  falls back to joining `city`, `region`, and `country` when `fullLocation` is
  absent. `location.country` is a two-letter lowercase code, so it is only used
  in that fallback.
- `remote` and `hybrid` are separate booleans, mapped to `workplace_type` of
  `remote` or `hybrid`. Neither being set leaves `workplace_type` as `None`
  rather than asserting onsite.
- The `ref` field is an API URL, not a careers-page URL, and the per-posting
  detail endpoint rejects the listing id with a 400. Hence the built URL.

## Workable

`GET https://apply.workable.com/api/v1/widget/accounts/{slug}`

```json
{
  "name": "Hugging Face",
  "description": "...",
  "jobs": [
    {
      "title": "Low-Level Senior Software Engineer, Xet Storage - US Remote",
      "shortcode": "002470F128",
      "url": "https://apply.workable.com/j/002470F128",
      "shortlink": "https://apply.workable.com/j/002470F128",
      "application_url": "https://apply.workable.com/j/002470F128/apply",
      "telecommuting": true,
      "country": "United States",
      "city": "New York",
      "state": "New York",
      "locations": [
        {"country": "United States", "countryCode": "US", "city": "New York", "region": "New York"}
      ]
    }
  ]
}
```

- Returns every published job in one response; no pagination parameters.
- `shortcode` is the id; there is no numeric `id`.
- Locations come from `locations[]` as `city, region, country`, falling back to
  the top-level `city`/`state`/`country`. Repeats are collapsed, so a New York
  city plus New York region yields `"New York, United States"`.
- `telecommuting` is the only workplace signal, so it drives both `is_remote`
  and a `workplace_type` of `remote`. There is no hybrid/onsite distinction.

## Recruitee

`GET https://{slug}.recruitee.com/api/offers/`

```json
{
  "offers": [
    {
      "id": 2751915,
      "title": "Customer Success Manager Benelux",
      "slug": "customer-success-manager-benelux-dutch-speaking-3",
      "status": "published",
      "careers_url": "https://jobs.channable.com/o/customer-success-manager-benelux-dutch-speaking-3",
      "careers_apply_url": "https://jobs.channable.com/o/customer-success-manager-benelux-dutch-speaking-3/c/new",
      "location": "Utrecht, Utrecht, Netherlands",
      "city": "Utrecht",
      "country": "Netherlands",
      "state_name": "Utrecht",
      "remote": false,
      "hybrid": true,
      "on_site": false,
      "locations": [
        {"name": "Utrecht", "city": "Utrecht", "state": "Utrecht", "country": "Netherlands"}
      ]
    }
  ]
}
```

- Returns every offer in one response; no pagination parameters.
- Responses are large because each offer embeds `open_questions`,
  `description`, `requirements`, and `translations`. The adapter ignores those.
- `status` is filtered to `published`, the same idea as Ashby's `isListed`.
- `remote`, `hybrid`, and `on_site` are three separate booleans, checked in that
  order for `workplace_type`.
- Locations come from `locations[]`, falling back to the pre-joined `location`
  string and then to `city`/`state_name`/`country`.

## Personio

`GET https://{slug}.jobs.personio.de/search.json`

Returns a bare array.

```json
[
  {
    "id": 2415353,
    "name": "(Senior) CRM Manager (m/w/d)",
    "employment_type": "Festanstellung",
    "seniority": "Berufserfahren",
    "office": "Berlin,Frankfurt am Main",
    "offices": ["Berlin", "Frankfurt am Main"],
    "schedule": "Vollzeit",
    "department": "Group - Marketing",
    "subcompany": "CLARK Holding SE"
  }
]
```

- No pagination; the array holds every published position.
- Title is `name`, not `title`.
- `offices` is the location list. The scalar `office` is those same names joined
  by commas with no spaces, so the fallback path splits it on commas rather than
  treating it as one `"City, Region"` string.
- There is no workplace-type field. `Remote` shows up as an office name, so
  `is_remote` and `workplace_type` are derived from the office text.
- Some boards sit behind a Vercel bot check that answers HTTP 429 with an HTML
  body. `get_json` retries those and the board is eventually skipped as an
  `ATSClientError`, which costs ~30s of backoff per affected board.

## BambooHR

`GET https://{slug}.bamboohr.com/careers/list`

```json
{
  "meta": {"totalCount": 10},
  "result": [
    {
      "id": "60",
      "jobOpeningName": "Executive Assistant to the CEO",
      "departmentLabel": "Executive",
      "employmentStatusLabel": "US Employee",
      "location": {"city": "chicago", "state": "Illinois"},
      "atsLocation": {"country": null, "state": null, "province": null, "city": null},
      "isRemote": null,
      "locationType": "2"
    }
  ]
}
```

- No pagination; `meta.totalCount` matches the length of `result`.
- Title is `jobOpeningName`.
- `locationType` is the workplace flag, as a string:

  | Value | `workplace_type` |
  |-------|------------------|
  | `"0"` | `onsite` |
  | `"1"` | `remote` |
  | `"2"` | `hybrid` |

- The two location fields are mutually exclusive in practice. Remote openings
  put their region in `atsLocation` (`city`, `state`, `province`, `country`) and
  leave `location` null; onsite and hybrid openings do the reverse. The adapter
  reads both and drops blanks. `atsLocation` often repeats one value across
  fields, as in `{"country": "Poland", "province": "Poland", "city": "Poland"}`,
  which collapses to `"Poland"`.
- A fully remote board can leave every location null (Fly.io does). Those jobs
  still satisfy the remote filter because `workplace_type` is `remote`, which
  `location_blob` in [`src/match.py`](../src/match.py) folds into the text it
  matches against.
- `isRemote` is null on every board sampled. It is still read as a fallback.
- City names are sometimes lowercase (`"chicago"`); matching is case folded.

## Pagination

Only SmartRecruiters needs it today, so it is configured per ATS in
[`config/ats.json`](../config/ats.json) rather than hard-coded:

```json
"smartrecruiters": {
  "enabled": true,
  "url": "https://api.smartrecruiters.com/v1/companies/{slug}/postings",
  "page": {"size": 100, "max_pages": 20}
}
```

An ATS with no `page` block is fetched with a single GET, which is what the
other eight do. `limit_param` and `offset_param` default to `limit` and
`offset` and can be overridden per ATS.

`LiveFetcher._fetch_pages` requests `offset = 0, size, 2 * size, …` and stops on
the first page holding fewer than `size` raw records. Exhaustion is measured
from raw record counts, not normalized `Job` counts, because `normalize` may
drop records and a short page of `Job`s would end the walk early. `max_pages`
bounds the walk and logs a warning when it is reached, so a very large board is
truncated rather than issuing 49 sequential requests.

## Workday (not implemented)

`POST https://{tenant}.{shard}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs`
with body `{"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}`.

```json
{
  "total": 2000,
  "jobPostings": [
    {
      "title": "Senior DFT Engineer",
      "externalPath": "/job/US-CA-Santa-Clara/Senior-DFT-Engineer_JR2000499",
      "locationsText": "US, CA, Santa Clara",
      "postedOn": "Posted Today",
      "bulletFields": ["JR2000499"]
    },
    {
      "title": "Graphics System Software Engineer",
      "externalPath": "/job/US-CA-Santa-Clara/Graphics-System-Software-Engineer_JR2026351",
      "locationsText": "2 Locations",
      "bulletFields": ["JR2026351"]
    }
  ]
}
```

Workday rows in `companies.json` carry `{"workday": {"tenant", "site", "shard"}}`
instead of a `slug`, and the ATS stays `"enabled": false`. Four things stand in
the way of a straightforward adapter:

1. **POST, not GET.** `src/clients/http.py` only has `get_json`.
2. **The URL needs three fields**, but `LiveFetcher` formats the template with
   `slug` alone.
3. **Pagination is in the JSON body, not the query string**, and `limit` must be
   20. Sending 50 or 100 returns an empty `jobPostings` with no `total`. With
   `total` reaching 2,000, a full walk is 100 sequential requests.
4. **Locations are frequently unusable.** About 60% of rows report
   `locationsText: "N Locations"` instead of a place, which no location filter
   can match. Real locations only come from a per-posting detail request:

   `GET /wday/cxs/{tenant}/{site}/job{externalPath}` returns
   `jobPostingInfo` with `location`, `additionalLocations`, `jobReqId`, and an
   absolute `externalUrl`.

The viable shape is a two-phase fetch: page the list, filter on title first,
then request detail only for the few titles that survive. That is a new
enrichment step in the pipeline, which is why Workday is tracked separately.
