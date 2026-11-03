// Port of backend/finn/push/digest.py. Keep the two in lockstep: lib/digest.test.ts runs this against
// backend/tests/fixtures/digest_cases.json, the frozen output of the Python version.
import type { Alert, Attachment, Digest, DigestCard, Filing, Tier } from "./types";

const TIER_RANK: Record<Tier, number> = { act: 2, know: 1, routine: 0 };
const FAMILY = new Set(["results", "earnings_call"]);
const LEADS = new Set(["filing", "board_outcome"]);

type F = Filing & { _dups?: Filing[] };

function card(f: Filing, attachments: Attachment[] = []): DigestCard {
  return {
    kind: "filing", id: f.id, symbol: f.symbol, category: f.category, subtype: f.subtype ?? null,
    tier: f.tier, score: Number(f.score), ts: f.ts, title: f.subject, card: f.card ?? null,
    reasons: [...(f.reasons ?? [])], url: f.url ?? null, attachments,
  };
}

function attachment(f: Filing): Attachment {
  return { subject: f.subject, url: f.url ?? null, category: f.category, ts: f.ts };
}

// Total orders identical to digest.py's _by_time / _by_score.
function byTime(a: { ts: string; id: string }, b: { ts: string; id: string }): number {
  if (a.ts !== b.ts) return a.ts > b.ts ? -1 : 1;
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
}
function byScore(a: DigestCard, b: DigestCard): number {
  if (a.score !== b.score) return a.score > b.score ? -1 : 1;
  return byTime(a, b);
}

export function buildDigest(filings: Filing[], start: string, end: string, alerts: Alert[] = []): Digest {
  const inside: F[] = filings
    .filter((f) => start <= f.ts && f.ts <= end)
    .map((f) => ({ ...f }))
    .sort((a, b) => (a.ts !== b.ts ? (a.ts > b.ts ? -1 : 1) : a.id > b.id ? -1 : a.id < b.id ? 1 : 0));

  // 1. Fold exact repeats.
  const seen = new Map<string, F>();
  const unique: F[] = [];
  for (const f of inside) {
    const key = `${f.symbol}\u0000${f.subject.trim().toLowerCase()}\u0000${f.ts.slice(0, 10)}`;
    const first = seen.get(key);
    if (first) {
      (first._dups ??= []).push(f);
      continue;
    }
    seen.set(key, f);
    unique.push(f);
  }

  // 2. Results family per company.
  const cards: DigestCard[] = [];
  const bySymbol = new Map<string, F[]>();
  for (const f of unique) {
    const list = bySymbol.get(f.symbol) ?? [];
    list.push(f);
    bySymbol.set(f.symbol, list);
  }
  for (const fs of bySymbol.values()) {
    const fam = fs.filter((f) => FAMILY.has(f.category));
    const hasResults = fam.some((f) => f.category === "results" && LEADS.has(f.subtype ?? ""));
    const rest = fs.filter((f) => !(hasResults && FAMILY.has(f.category)));
    if (hasResults) {
      const notLead = (f: F) => (f.category !== "results" || !LEADS.has(f.subtype ?? "") ? 1 : 0);
      fam.sort((a, b) => notLead(a) - notLead(b) || Number(b.score) - Number(a.score) || (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0));
      const [lead, ...others] = fam;
      const atts = [...others.map(attachment), ...fam.flatMap((o) => (o._dups ?? []).map(attachment))];
      const c = card(lead, atts);
      c.tier = fam.map((f) => f.tier).reduce((m, t) => (TIER_RANK[t] > TIER_RANK[m] ? t : m));
      c.score = Math.max(...fam.map((f) => Number(f.score)));
      if (atts.length) {
        c.reasons.push(`${atts.length} related filing${atts.length > 1 ? "s" : ""} folded in (deck, call, press release)`);
      }
      cards.push(c);
    }
    for (const f of rest) cards.push(card(f, (f._dups ?? []).map(attachment)));
  }

  const act = cards.filter((c) => c.tier === "act").sort(byScore);
  const know = cards.filter((c) => c.tier === "know").sort(byScore);
  const routine = cards.filter((c) => c.tier === "routine").sort(byTime);

  const alertCards = [...alerts].sort((a, b) => (a.ts > b.ts ? -1 : a.ts < b.ts ? 1 : 0));
  const byCompany: Record<string, { title: string; url: string | null; ts: string }[]> = {};
  for (const c of routine) (byCompany[c.symbol] ??= []).push({ title: c.title, url: c.url, ts: c.ts });
  const sortedByCompany = Object.fromEntries(Object.keys(byCompany).sort().map((k) => [k, byCompany[k]]));

  return {
    window: { start, end },
    headline: {
      act: act.length + alertCards.length, know: know.length, routine: routine.length,
      filings: inside.length, companies: new Set(inside.map((f) => f.symbol)).size,
    },
    alerts: alertCards, act, know,
    routine: { count: routine.length, companies: Object.keys(byCompany).length, by_company: sortedByCompany },
  };
}
