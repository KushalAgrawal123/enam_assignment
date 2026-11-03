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
}

export type DataMode = "live" | "demo";

export interface BriefData {
  mode: DataMode;
  asOf: string; // window end: now (live) or the freeze time (demo)
  freezeTime: string | null;
  filings: Filing[];
  companies: Record<string, Company>;
  prices: Record<string, PricePoint[]>;
  fallbackReason: string | null;
}
