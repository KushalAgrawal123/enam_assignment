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

export function ResearchView({ symbol }: { symbol: string }) {
  const [state, setState] = useState<Loaded | null>(null);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const started = useRef(false);

  useEffect(() => {
    let alive = true;
    research(symbol)
      .then((l) => alive && setState(l))
      .catch((e) => alive && setError({ code: e instanceof ApiError ? e.code : "error", message: e.message }));
    return () => { alive = false; };
  }, [symbol]);

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
          <h1 className="font-serif text-[28px] leading-tight">{p.name}</h1>
          <p className="mt-1 text-[12px] text-muted">
            Numbers from screener.in tables as of <span className="num">{stamp(p.as_of)}</span> IST{state.demo ? " · demo copy" : ""}.
            {d && <> Sources: <span className="num">{d.transcripts}</span> call transcripts{d.annual_report ? `, annual report ${d.annual_report}` : ""}
              {d.pending > 0 && !state.demo ? <span className="text-ink"> · reading {d.pending} more</span> : null}
              {d.ocr_needed > 0 ? ` · ${d.ocr_needed} scanned (not readable yet)` : ""}.</>}
          </p>
        </header>
        <nav className="sticky top-[env(safe-area-inset-top)] z-10 -mx-4 mt-3 flex gap-1.5 overflow-x-auto bg-paper/95 px-4 py-2 backdrop-blur">
          {SECTIONS.map(([id, label]) => (
            <a key={id} href={`#${id}`} className="shrink-0 rounded-full border border-hairline px-3 py-1 text-[12px] text-muted hover:text-ink">{label}</a>
          ))}
        </nav>
        <div className="mt-2 space-y-3">
          <VerdictCard card={p.cards.verdict} />
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

function ResearchSkeleton({ symbol }: { symbol: string }) {
  return (
    <main aria-busy>
      <p className="num text-[12px] text-muted">{symbol}</p>
      <p className="mt-1 font-serif text-[22px] text-muted">Reading the latest numbers…</p>
      <div className="animate-pulse">{[0, 1, 2].map((i) => <div key={i} className="mt-4 h-40 rounded-xl bg-hairline" />)}</div>
    </main>
  );
}
