// Data layer (BUILD_PLAN §6.3): live Supabase first, the frozen demo snapshot otherwise.
// Falls back when Supabase isn't configured, a request fails, or the newest filing is older than 72 hours.
import { supabase } from "./supabase";
import type { BriefData, Company, DataMode, Filing, PricePoint, Snapshot } from "./types";

const STALE_MS = 72 * 3600 * 1000;
const HISTORY_DAYS = 8; // the widest preset window is 7d; custom ranges reload with their own start
const FILING_COLS = "id,symbol,ts,subject,url,category,subtype,secondary,score,tier,reasons,card,card_status";

const z = (d: Date) => d.toISOString().replace(/\.\d{3}Z$/, "Z");

function index(companies: Company[], prices: PricePoint[]) {
  const c: Record<string, Company> = {};
  for (const x of companies) c[x.symbol] = x;
  const p: Record<string, PricePoint[]> = {};
  for (const x of prices) (p[x.symbol] ??= []).push({ ...x, close: Number(x.close) });
  for (const k of Object.keys(p)) p[k].sort((a, b) => (a.date < b.date ? -1 : 1));
  return { c, p };
}

const normFiling = (f: Filing): Filing => ({ ...f, ts: z(new Date(f.ts)), score: Number(f.score) });

async function loadLive(since: Date): Promise<BriefData> {
  const sb = supabase();
  if (!sb) throw new Error("Supabase isn't configured for this deployment");
  const now = new Date();
  const priceSince = new Date(now.getTime() - 60 * 86400 * 1000).toISOString().slice(0, 10);
  const [f, c, p] = await Promise.all([
    sb.from("filings").select(FILING_COLS).gte("ts", since.toISOString()).order("ts", { ascending: false }).limit(2000),
    sb.from("companies").select("symbol,name,sector,mcap_cr,is_financial,in_portfolio,in_research_set"),
    sb.from("prices").select("symbol,date,close,volume").gte("date", priceSince).order("date").limit(5000),
  ]);
  const err = f.error ?? c.error ?? p.error;
  if (err) throw new Error(err.message);
  const filings = (f.data as Filing[]).map(normFiling);
  const newest = filings[0]?.ts;
  if (!newest || now.getTime() - new Date(newest).getTime() > STALE_MS) {
    throw new Error("Live data is more than 72 hours old");
  }
  const { c: companies, p: prices } = index(c.data as Company[], p.data as PricePoint[]);
  return { mode: "live", asOf: z(now), freezeTime: null, filings, companies, prices, fallbackReason: null };
}

let snapshotPromise: Promise<Snapshot> | null = null;

async function loadDemo(reason: string | null): Promise<BriefData> {
  snapshotPromise ??= fetch("/demo/snapshot.json").then((r) => {
    if (!r.ok) throw new Error(`demo snapshot missing (${r.status})`);
    return r.json() as Promise<Snapshot>;
  });
  const s = await snapshotPromise;
  const { c, p } = index(s.companies, s.prices);
  return {
    mode: "demo", asOf: s.freeze_time, freezeTime: s.freeze_time, filings: s.filings.map(normFiling),
    companies: c, prices: p, fallbackReason: reason,
  };
}

/** Load the Brief. `prefer` is the user's choice from the Data chip; live failures always fall back to demo. */
export async function loadBrief(prefer: DataMode, windowStart?: Date): Promise<BriefData> {
  if (prefer === "demo") return loadDemo(null);
  const since = windowStart ?? new Date(Date.now() - HISTORY_DAYS * 86400 * 1000);
  try {
    return await loadLive(since);
  } catch (e) {
    return loadDemo(e instanceof Error ? e.message : String(e));
  }
}

export const liveConfigured = () => supabase() !== null;
