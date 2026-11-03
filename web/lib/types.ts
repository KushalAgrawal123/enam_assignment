// Contracts shared with the backend (BUILD_PLAN §4.2). Phase 1 uses the Push half.

export type Tier = "act" | "know" | "routine";

export interface Filing {
  id: string;
  symbol: string;
  ts: string; // ISO-8601 UTC
  subject: string;
  url: string | null;
  category: string;
  subtype: string | null;
  secondary?: string[] | null;
  score: number;
  tier: Tier;
  reasons: string[];
  card: unknown | null;
  card_status?: string;
}

export interface Alert {
  id: number;
  symbol: string;
  kind: string;
  ts: string;
  title: string;
  reasons: string[];
  payload: Record<string, unknown>;
  seen: boolean;
}

export interface Attachment {
  subject: string;
  url: string | null;
  category: string;
  ts: string;
}

export interface DigestCard {
  kind: "filing" | "alert";
  id: string;
  symbol: string;
  category: string;
  subtype: string | null;
  tier: Tier;
  score: number;
  ts: string;
  title: string;
  card: unknown;
  reasons: string[];
  url: string | null;
  attachments: Attachment[];
}

export interface Digest {
  window: { start: string; end: string };
  headline: { act: number; know: number; routine: number; filings: number; companies: number };
  alerts: Alert[];
  act: DigestCard[];
  know: DigestCard[];
  routine: {
    count: number;
    companies: number;
    by_company: Record<string, { title: string; url: string | null; ts: string }[]>;
  };
}

export interface Company {
  symbol: string;
  name: string;
  sector: string | null;
  mcap_cr: number | null;
  is_financial: boolean;
  in_portfolio: boolean;
  in_research_set: boolean;
}

export interface PricePoint {
  symbol: string;
  date: string;
  close: number;
  volume: number | null;
}

export interface Snapshot {
  freeze_time: string;
  companies: Company[];
  filings: Filing[];
  prices: PricePoint[];
  alerts: Alert[];
  settings?: Settings;
}

export type DataMode = "live" | "demo";

export interface BriefData {
  mode: DataMode;
  asOf: string; // window end: now (live) or the freeze time (demo)
  freezeTime: string | null;
  filings: Filing[];
  companies: Record<string, Company>;
  prices: Record<string, PricePoint[]>;
  alerts: Alert[];
  fallbackReason: string | null;
}

// ---- Pull (Phase 2) ----
export type ResearchCardId = "verdict" | "ledger" | "narrative" | "snapshot" | "financials"
  | "trajectory" | "balance_sheet" | "cash_quality" | "guidance" | "bull_bear";

export interface Citation {
  id: string;
  kind: "transcript" | "annual_report" | "results" | "filing" | "table";
  doc_url?: string; period?: string; page?: number; quote?: string;
  table_ref?: { section: string; metric: string; period: string; value: number | null };
}

export interface ResearchCard<T = unknown> {
  id: ResearchCardId; status: "queued" | "running" | "ready" | "gap" | "failed";
  data: T | null; citations: Citation[]; gaps: string[];
}

export interface Cell { value: number; period: string; metric?: string; citation?: string; citations?: string[] }
export interface Item extends Cell { label: string; unit: string; derived?: string }

export interface ResearchPayload {
  symbol: string; name: string; basis: "consolidated" | "standalone" | null; is_financial: boolean;
  as_of: string; status: "queued" | "running" | "ready" | "partial";
  cards: Partial<Record<ResearchCardId, ResearchCard>>; gaps: string[];
  documents?: { transcripts: number; annual_report: string | null; ocr_needed: number; failed: number; pending: number };
}

export interface TableReceipt {
  kind: "table"; doc_url: string; section: string; metric: string; periods: string[];
  values: (number | null)[]; highlight: number; basis: string | null;
}

// ---- Push cards (Phase 3) ----
export interface ResultsCard {
  type: "results"; period_end: string; basis: "consolidated" | "standalone" | null;
  source: "xbrl" | "pdf" | "screener"; verified: boolean; issues: string[]; flags: string[];
  rows: { metric: string; value_cr: number | null; qoq_pct: number | null; yoy_pct: number | null }[];
  margin: { ebitda_margin_pct?: number; qoq_bps?: number | null; yoy_bps?: number | null };
  compare: { qoq: string | null; yoy: string | null };
  ebitda_note: string | null; url: string | null; page: number | null;
}
export interface Person {
  name: string; role: string | null; role_class: string | null;
  action: "appointment" | "resignation" | "cessation" | "redesignation" | "retirement";
  effective_date: string | null; reason: string | null; page: number | null;
  bio: { headline: string | null; bullets: { text: string; url: string }[];
         sources?: { url: string; title: string }[]; note?: string } | null;
}
export interface MgmtCard { type: "management_change"; outgoing: Person[]; incoming: Person[]; flags: string[]; url: string | null }
export interface OneLinerCard { type: "oneliner"; category: string; line: string;
  facts: Record<string, string | number | null>; url: string | null; page: number | null }
export type PushCard = ResultsCard | MgmtCard | OneLinerCard;

export interface AlertPayload { date: string; close: number; ret_pct: number | null; index_ret_pct: number | null;
  vol_x: number | null; likely_cause: { subject: string; url: string | null; category: string } | null;
  filing_id?: string; url?: string | null; category?: string; tier?: string }

export interface Settings {
  vol_multiple: number; vol_lookback: number; min_avg_volume: number; price_move_pct: number;
  relative_to_index: boolean; alert_categories: string[]; min_category_tier: "act" | "know" | "routine";
  overrides: Record<string, Record<string, number | boolean>>; weights: Record<string, number>;
}
