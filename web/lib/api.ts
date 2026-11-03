// Pull API client. Falls back to the frozen demo payloads when the API is unreachable (BUILD_PLAN §6.3).
import type { ResearchPayload, TableReceipt } from "./types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

export class ApiError extends Error {
  constructor(public code: string, message: string, public status = 0) { super(message); }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API) throw new ApiError("no_api", "The research API isn't configured for this deployment");
  const r = await fetch(API + path, { ...init, cache: "no-store" });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(body.error ?? "http_error", body.detail ?? `HTTP ${r.status}`, r.status);
  return body as T;
}

export type Loaded = { payload: ResearchPayload; demo: boolean; reason?: string };

export async function research(symbol: string, refresh = false): Promise<Loaded> {
  try {
    return { payload: await call<ResearchPayload>(`/research/${symbol}${refresh ? "?refresh=1" : ""}`, { method: "POST" }), demo: false };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) throw e; // a real "not an NSE symbol" answer
    const r = await fetch(`/demo/research/${symbol}.json`);
    if (r.ok) return { payload: await r.json(), demo: true, reason: (e as Error).message };
    throw e;
  }
}

export const refreshPayload = (symbol: string) => call<ResearchPayload>(`/research/${symbol}`);
export const ingest = (symbol: string) => call<{ done: boolean }>(`/research/${symbol}/ingest`, { method: "POST" });

export async function tableReceipt(symbol: string, citationId: string, payload?: ResearchPayload): Promise<TableReceipt | null> {
  try {
    return await call<TableReceipt>(`/receipt?symbol=${encodeURIComponent(symbol)}&citation_id=${encodeURIComponent(citationId)}`);
  } catch {
    // Offline/demo: show at least the cited cell from the payload itself.
    for (const card of Object.values(payload?.cards ?? {})) {
      const c = card?.citations.find((x) => x.id === citationId);
      if (c?.table_ref) {
        return { kind: "table", doc_url: `https://www.screener.in/company/${symbol}/`, section: c.table_ref.section,
          metric: c.table_ref.metric, periods: [c.table_ref.period], values: [c.table_ref.value], highlight: 0, basis: null };
      }
    }
    return null;
  }
}
