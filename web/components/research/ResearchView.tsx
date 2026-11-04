"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { analyse, ApiError, ingest, refreshPayload, research, type Loaded } from "@/lib/api";
import { stamp } from "@/lib/format";
import type { ResearchPayload } from "@/lib/types";
import { BullBearCard, GuidanceCard, LedgerCard, NarrativeCard, SnapshotCard, VerdictCard } from "./AnalysisCards";
import { BalanceCard, CashCard, FinancialsCard, TrajectoryCard } from "./NumberCards";
import { ReceiptProvider } from "./Receipt";

// Verdict first, then the evidence behind it (BUILD_PLAN Phase 3 web).
const SECTIONS = [["verdict", "Verdict"], ["ledger", "Promises"], ["narrative", "Narrative"], ["snapshot", "Business"],
  ["financials", "Numbers"], ["trajectory", "Trajectory"], ["balance_sheet", "Balance sheet"], ["cash_quality", "Cash"],
  ["guidance", "Guidance"], ["bull_bear", "Bull/bear"]];

const needsAnalysis = (p: ResearchPayload) => !p.cards.verdict;

const FRESH_MS = 24 * 3600 * 1000;

export function ResearchView({ symbol, initial = null }: { symbol: string; initial?: ResearchPayload | null }) {
  const [state, setState] = useState<Loaded | null>(initial ? { payload: initial, demo: false } : null);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const started = useRef(false);

  useEffect(() => {
    // Built within the last day on the server: nothing to (re)build here; the documents effect below takes over.
    if (initial && Date.now() - new Date(initial.as_of).getTime() < FRESH_MS) return;
    let alive = true;
    research(symbol)
      .then((l) => alive && setState(l))
      .catch((e) => alive && setError({ code: e instanceof ApiError ? e.code : "error", message: e.message }));
    return () => { alive = false; };
  }, [symbol, initial]);

  // Documents (transcripts, annual report) load in the background, then the analysis cards are built from them.
  useEffect(() => {
    if (!state || state.demo || started.current) return;
    const p = state.payload;
    if (!p.documents?.pending && !needsAnalysis(p)) return;
    started.current = true;
    let alive = true;
    const update = () => refreshPayload(symbol).then((x) => alive && setState({ payload: x, demo: false })).catch(() => {});
    const poll = setInterval(update, 4000);
    (async () => {
      for (let i = 0; i < 4; i++) {           // ingest is resumable; each call has its own time budget
        const r = await ingest(symbol).catch(() => ({ done: true }));
        if (r.done) break;
      }
      await analyse(symbol).catch(() => {});
    })().finally(() => { clearInterval(poll); update(); });
    return () => { alive = false; clearInterval(poll); };
  }, [state, symbol]);

  if (error) return (
    <main className="pt-10">
      <p className="font-serif text-[22px]">{error.code === "unknown_symbol" ? `${symbol} isn't an NSE symbol` : `Couldn't research ${symbol}`}</p>
      <p className="mt-2 text-muted">{error.code === "unknown_symbol" ? "Check the ticker, or search by company name." : error.message}</p>
      <Link href="/lookup" className="mt-4 inline-block underline underline-offset-2">Back to Look up</Link>
    </main>
  );
  if (!state) return <ResearchSkeleton symbol={symbol} />;

  const p = state.payload;
  const d = p.documents;
  const analysing = !state.demo && (needsAnalysis(p) || (d?.pending ?? 0) > 0);
  return (
    <ReceiptProvider symbol={p.symbol} payload={p}>
      <main>
        <header>
          <p className="num text-[12px] text-muted">{p.symbol} · {p.basis ?? "—"}{p.is_financial ? " · bank/NBFC" : ""}</p>
          <h1 className="font-serif text-[30px] leading-tight">{p.name}</h1>
          <p className="mt-1 text-[12px] text-muted">
            Numbers from screener.in tables as of <span className="num">{stamp(p.as_of)}</span> IST{state.demo ? " · demo copy" : ""}.
            {d && <> Sources: <span className="num">{d.transcripts}</span> call transcripts{d.annual_report ? `, annual report ${d.annual_report}` : ""}
              {d.pending > 0 && !state.demo ? <span className="text-ink"> · reading {d.pending} more</span> : null}
              {d.ocr_needed > 0 ? ` · ${d.ocr_needed} scanned (not readable yet)` : ""}.</>}
          </p>
        </header>
        <KeyStats card={p.cards.financials} />
        <SectionChips ids={SECTIONS} />
        <div className="mt-2 space-y-3">
          <VerdictCard card={p.cards.verdict} ledger={p.cards.ledger}
            rules={["ledger", "narrative", "guidance", "bull_bear"].some((k) => (p.cards[k as keyof typeof p.cards]?.data as { method?: string } | null)?.method === "rules")} />
          {analysing && <p className="text-center text-[12px] text-muted">Reading the earnings calls and annual report…</p>}
          <LedgerCard card={p.cards.ledger} />
          <NarrativeCard card={p.cards.narrative} />
          <SnapshotCard card={p.cards.snapshot} />
          <FinancialsCard card={p.cards.financials} />
          <TrajectoryCard card={p.cards.trajectory} />
          <BalanceCard card={p.cards.balance_sheet} />
          <CashCard card={p.cards.cash_quality} />
          <GuidanceCard card={p.cards.guidance} />
          <BullBearCard card={p.cards.bull_bear} />
        </div>
        <p className="mt-6 text-center text-[11px] text-muted">Primary sources only: exchange filings, the company&apos;s calls and annual report, and reported tables. No news, no web search.</p>
      </main>
    </ReceiptProvider>
  );
}

export function ResearchSkeleton({ symbol }: { symbol: string }) {
  return (
    <main aria-busy>
      <p className="num text-[12px] text-muted">{symbol}</p>
      <p className="mt-1 font-serif text-[22px] text-muted">Reading the latest numbers…</p>
      <div className="animate-pulse">{[0, 1, 2].map((i) => <div key={i} className="mt-4 h-40 rounded-xl bg-hairline" />)}</div>
    </main>
  );
}

type FinItem = { label: string; value: number; unit: string };
const compactCr = (v: number) => v >= 1e5 ? `₹${(v / 1e5).toFixed(2)}L cr` : `₹${Math.round(v).toLocaleString("en-IN")} cr`;

/** Four headline numbers under the name: size, scale, profitability, returns. */
function KeyStats({ card }: { card?: ResearchPayload["cards"]["financials"] }) {
  const items = ((card?.data as { items?: FinItem[] } | null)?.items ?? []);
  const pick = (...labels: string[]) => labels.map((l) => items.find((i) => i.label === l)).find(Boolean);
  const stats = [["Market cap", pick("Market cap")], ["Revenue TTM", pick("Revenue (TTM)")],
    ["Margin", pick("EBITDA margin (OPM)", "Financing margin")], ["Return", pick("ROCE", "ROE")]] as const;
  if (!items.length) return null;
  return (
    <dl className="card mt-3 grid grid-cols-2 gap-px overflow-hidden bg-hairline p-0 sm:grid-cols-4">
      {stats.map(([label, it]) => (
        <div key={label} className="bg-raised px-3.5 py-2.5">
          <dt className="text-[10px] uppercase tracking-wider text-muted">{label === "Return" && it ? it.label : label}</dt>
          <dd className="num mt-0.5 text-[17px] font-medium">
            {!it ? "—" : it.unit === "₹ cr" ? compactCr(it.value) : `${it.value}${it.unit === "%" ? "%" : ""}`}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Sticky section chips; the one on screen is highlighted and kept in view. */
function SectionChips({ ids }: { ids: string[][] }) {
  const [active, setActive] = useState(ids[0][0]);
  const nav = useRef<HTMLElement>(null);
  useEffect(() => {
    const els = ids.map(([id]) => document.getElementById(id)).filter((e): e is HTMLElement => !!e);
    const io = new IntersectionObserver((entries) => {
      const top = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (top) setActive(top.target.id);
    }, { rootMargin: "-120px 0px -55% 0px" });
    els.forEach((e) => io.observe(e));
    return () => io.disconnect();
  }, [ids]);
  useEffect(() => {
    nav.current?.querySelector(`[data-id="${active}"]`)?.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
  }, [active]);
  return (
    <nav ref={nav} aria-label="Sections"
      className="sticky top-[env(safe-area-inset-top)] z-20 -mx-4 mt-3 flex gap-1.5 overflow-x-auto bg-paper/90 px-4 py-2 backdrop-blur [scrollbar-width:none]">
      {ids.map(([id, label]) => (
        <a key={id} href={`#${id}`} data-id={id} aria-current={active === id ? "true" : undefined}
          className={`shrink-0 rounded-full border px-3 py-1 text-[12px] transition-colors ${active === id ? "border-ink bg-ink text-paper" : "border-hairline text-muted hover:text-ink"}`}>{label}</a>
      ))}
    </nav>
  );
}
