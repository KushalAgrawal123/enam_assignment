// Pull API client. Falls back to the frozen demo payloads when the API is unreachable (BUILD_PLAN §6.3).
import type { AnyReceipt, AskAnswer, Citation, ResearchPayload, TableReceipt } from "./types";

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
export const analyse = (symbol: string) => call<{ cards?: Record<string, string> }>(`/research/${symbol}/analyse`, { method: "POST" });

const findCitation = (payload: ResearchPayload | undefined, id: string): Citation | undefined => {
  for (const card of Object.values(payload?.cards ?? {})) {
    const c = card?.citations.find((x) => x.id === id);
    if (c) return c;
  }
};

/** Any receipt: a table row (TBL-…) or a document page (T…/AR…) with the quote highlighted. */
export async function receipt(symbol: string, id: string, payload?: ResearchPayload, quote?: string): Promise<AnyReceipt | null> {
  if (id.startsWith("TBL-")) return tableReceipt(symbol, id, payload);
  const c = findCitation(payload, id);
  const q = quote ?? c?.quote;
  try {
    return await call<AnyReceipt>(`/receipt?symbol=${encodeURIComponent(symbol)}&citation_id=${encodeURIComponent(id)}${q ? `&q=${encodeURIComponent(q)}` : ""}`);
  } catch {
    if (!c && !q) return null;   // offline: the quote we stored is the receipt
    const text = (q ?? "").replace(/ …$/, "");
    return { kind: c?.kind === "annual_report" ? "annual_report" : "transcript", doc_url: c?.doc_url ?? "", period: c?.period ?? "",
      page: c?.page ?? 0, text, highlight: [0, text.length], citation_id: id, offline: true };
  }
}

export const askFinn = (symbol: string, question: string, context?: { card?: string; citation_id?: string }) =>
  local<AskAnswer>("/api/ask", "POST", { symbol, question, context });

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

// ---- writes (Phase 3) go through this app's own server routes, which hold the API token server-side. ----
async function local<T>(path: string, method: string, body?: unknown): Promise<T> {
  const r = await fetch(path, { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(data.error ?? "http_error", data.detail ?? `HTTP ${r.status}`, r.status);
  return data as T;
}

export const getSettings = () => call<import("./types").Settings>("/settings");
export const putSettings = (patch: Partial<import("./types").Settings>) => local<import("./types").Settings>("/api/settings", "PUT", patch);
export const markAlertSeen = (id: number) => local<{ ok: boolean }>(`/api/alerts/${id}/seen`, "POST");
