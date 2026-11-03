-- FINN schema. BUILD_PLAN §4.1, plus llm_cache (PLAN Delta 5) and meta (job bookkeeping).
-- Idempotent: safe to re-run.

create table if not exists companies (
  symbol text primary key, name text, isin text unique, bse_code text, sector text,
  mcap_cr numeric, is_financial boolean default false,
  in_portfolio boolean default false, in_research_set boolean default false,
  updated_at timestamptz default now());

create table if not exists prices (
  symbol text references companies, date date, open numeric, high numeric, low numeric,
  close numeric, volume bigint, primary key (symbol, date));

create table if not exists filings (
  id text primary key,                       -- 'BSE-<newsid>' | 'NSE-<seq_id>'
  symbol text references companies, isin text, ts timestamptz not null,
  subject text, text text, url text, src text,
  category text, subtype text, secondary text[], method text,
  score numeric, tier text check (tier in ('act','know','routine')), reasons text[],
  card jsonb,
  card_status text default 'none',            -- none|pending|ready|failed
  created_at timestamptz default now());
create index if not exists filings_ts on filings (ts desc);
create index if not exists filings_symbol_ts on filings (symbol, ts desc);

create table if not exists alerts (
  id bigserial primary key, dedupe text unique, symbol text, kind text,
  ts timestamptz default now(), title text, reasons text[], payload jsonb,
  seen boolean default false, sent boolean default false);

create table if not exists settings (
  id int primary key default 1 check (id = 1),
  vol_multiple numeric default 2, vol_lookback int default 20, min_avg_volume numeric default 10000,
  price_move_pct numeric default 5, relative_to_index boolean default false,
  alert_categories text[] default '{results,M&A,management_change,litigation,pledging,credit_rating}',
  min_category_tier text default 'know',
  overrides jsonb default '{}',
  weights jsonb default '{}',
  updated_at timestamptz default now());
insert into settings (id) values (1) on conflict do nothing;

create table if not exists docs (
  url text primary key, symbol text, kind text,
  period text, pages jsonb, sections jsonb,
  ocr_needed boolean default false, fetched_at timestamptz default now());

create table if not exists analyses (
  symbol text, card text, status text,
  data jsonb, citations jsonb, gaps text[], prompt_version text,
  updated_at timestamptz default now(), primary key (symbol, card));

create table if not exists jobs (
  id uuid primary key default gen_random_uuid(), symbol text, kind text default 'research',
  status text, error text, started_at timestamptz default now(), finished_at timestamptz);

-- LLM response cache + cost log, shared by every runtime (local, GitHub Actions, HF Spaces).
create table if not exists llm_cache (
  key text primary key,                       -- sha256(model|prompt_version|system|prompt)
  tier text, model text, prompt_version text,
  response jsonb, tokens_in int, tokens_out int, cost_inr numeric,
  hits int default 0, created_at timestamptz default now());

-- Small key/value store for job bookkeeping (last poll time, snapshot metadata).
create table if not exists meta (key text primary key, value jsonb, updated_at timestamptz default now());

-- Read access for the PWA (Supabase 'anon' role = publishable key). docs, llm_cache, meta stay private.
do $$ declare t text; begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    foreach t in array array['companies','prices','filings','alerts','settings','analyses','jobs'] loop
      execute format('alter table %I enable row level security', t);
      if not exists (select 1 from pg_policies where tablename = t and policyname = 'anon_read') then
        execute format('create policy anon_read on %I for select using (true)', t);
      end if;
    end loop;
    foreach t in array array['docs','llm_cache','meta'] loop
      execute format('alter table %I enable row level security', t);
    end loop;
  end if;
end $$;

-- NSE's own category for a filing ("Outcome of Board Meeting", ...): the classifier's first hint.
alter table filings add column if not exists exch_category text;
alter table filings add column if not exists has_xbrl boolean default false;
