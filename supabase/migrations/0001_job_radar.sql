-- KAN-24: job radar schema for the Set B feed.
--
-- Two tables (companies, jobs) and one RPC (search_jobs). The app calls
-- search_jobs with the phrases the user picked; matching happens here, not in
-- the client. anon and authenticated can only execute search_jobs. The service
-- role (KAN-25 exporter) owns all writes.
--
-- down: drop function search_jobs(text[], text[], text[]);
--       drop function phrase_pattern(text);
--       drop function set_updated_at() cascade;
--       drop table jobs;
--       drop table companies;
--       drop type workplace_type;

create type workplace_type as enum ('remote', 'hybrid', 'onsite');

create table companies (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  ats text not null,
  slug text not null default '',
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (ats, slug)
);

-- unique (company_id, external_id) leads with company_id, so the foreign key
-- needs no separate index.
create table jobs (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies (id),
  external_id text not null,
  title text not null,
  url text not null,
  locations text[] not null default '{}',
  workplace_type workplace_type,
  salary_text text,
  posted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (company_id, external_id)
);

-- The feed sorts on listed_at = coalesce(posted_at, created_at). Boards with no
-- publish time (Personio, BambooHR) are listed by when the exporter first saw them.
create index jobs_feed_order
  on jobs ((coalesce(posted_at, created_at)) desc, id);

create function set_updated_at() returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger companies_set_updated_at
  before update on companies
  for each row execute function set_updated_at();

create trigger jobs_set_updated_at
  before update on jobs
  for each row execute function set_updated_at();

-- Turns a user phrase into a case-insensitive whole-phrase regex.
-- Every non-alphanumeric character is escaped, so c++, .net, c#, (, [ and |
-- match literally. Lookarounds replace \m and \M, which fail next to symbols.
create function phrase_pattern(phrase text) returns text
language sql
immutable
strict
as $$
  select '(?<![[:alnum:]_])'
      || regexp_replace(phrase, '([^[:alnum:]])', '\\\1', 'g')
      || '(?![[:alnum:]_])'
$$;

-- One request per Apply. An empty array skips that category; blank phrases are
-- ignored. OR inside a category, AND across categories. Level and domain
-- phrases match the title. Location phrases match any location or the
-- workplace type. Newest first, at most 100 rows, enabled companies only.
create function search_jobs(
  levels text[] default '{}',
  domains text[] default '{}',
  locations text[] default '{}'
)
returns table (
  id uuid,
  title text,
  company_name text,
  location_label text,
  salary_text text,
  posted_at timestamptz,
  listed_at timestamptz,
  url text
)
language sql
stable
security definer
set search_path = public
as $$
  with q as (
    select
      array(select btrim(p) from unnest(levels) as p where btrim(p) <> '') as levels,
      array(select btrim(p) from unnest(domains) as p where btrim(p) <> '') as domains,
      array(select btrim(p) from unnest(locations) as p where btrim(p) <> '') as locations
  )
  select
    j.id,
    j.title,
    c.name as company_name,
    coalesce(j.locations[1], j.workplace_type::text) as location_label,
    j.salary_text,
    j.posted_at,
    coalesce(j.posted_at, j.created_at) as listed_at,
    j.url
  from jobs as j
  join companies as c on c.id = j.company_id
  cross join q
  where c.enabled
    and (
      cardinality(q.levels) = 0
      or exists (
        select 1 from unnest(q.levels) as p
        where j.title ~* phrase_pattern(p)
      )
    )
    and (
      cardinality(q.domains) = 0
      or exists (
        select 1 from unnest(q.domains) as p
        where j.title ~* phrase_pattern(p)
      )
    )
    and (
      cardinality(q.locations) = 0
      or exists (
        select 1 from unnest(q.locations) as p
        where j.workplace_type::text ~* phrase_pattern(p)
           or exists (
             select 1 from unnest(j.locations) as l
             where l ~* phrase_pattern(p)
           )
      )
    )
  order by coalesce(j.posted_at, j.created_at) desc, j.id
  limit 100
$$;

-- RLS on with no policies: the tables are closed to anon and authenticated.
-- The service role bypasses RLS and keeps full table access for the exporter.
alter table companies enable row level security;
alter table jobs enable row level security;

revoke all on table companies, jobs from public, anon, authenticated;
grant all on table companies, jobs to service_role;

revoke all on function set_updated_at() from public, anon, authenticated;
revoke all on function phrase_pattern(text) from public, anon, authenticated;
revoke all on function search_jobs(text[], text[], text[]) from public, anon, authenticated;
grant execute on function search_jobs(text[], text[], text[]) to anon, authenticated, service_role;
