"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { receipt } from "@/lib/api";
import { fmt, periodLabel } from "@/lib/format";
import type { AnyReceipt, DocReceipt, ResearchPayload, TableReceipt } from "@/lib/types";
import { AskSheet } from "./AskSheet";

// Every number and claim has a receipt: tap it and the sheet shows the table row with the cited cell marked,
// or the document page with the quote highlighted.
type Open = (citationIds: string[], unit: string, note?: string) => void;
type Ask = (context?: { card?: string; citation_id?: string }) => void;
const Ctx = createContext<{ open: Open; ask: Ask }>({ open: () => {}, ask: () => {} });
export const useReceipt = () => useContext(Ctx).open;
export const useAsk = () => useContext(Ctx).ask;

const SECTION = { "profit-loss": "Profit & loss (annual)", quarters: "Quarterly results", "balance-sheet": "Balance sheet",
  "cash-flow": "Cash flow", ratios: "Ratios", "Key ratios": "Key ratios" } as Record<string, string>;

export function ReceiptProvider({ symbol, payload, children }: { symbol: string; payload: ResearchPayload; children: ReactNode }) {
  const [req, setReq] = useState<{ ids: string[]; unit: string; note?: string } | null>(null);
  const [rows, setRows] = useState<(AnyReceipt | null)[] | null>(null);
  const [asking, setAsking] = useState<{ card?: string; citation_id?: string } | null>(null);
  const open: Open = useCallback((ids, unit, note) => { setRows(null); setReq({ ids, unit, note }); }, []);
  const ask: Ask = useCallback((context) => { setReq(null); setAsking(context ?? {}); }, []);

  useEffect(() => {
    if (!req) return;
    let alive = true;
    Promise.all(req.ids.map((id) => receipt(symbol, id, payload))).then((r) => alive && setRows(r));
    return () => { alive = false; };
  }, [req, symbol, payload]);

  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && (setReq(null), setAsking(null));
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, []);

  const docId = req?.ids.find((i) => !i.startsWith("TBL-"));
  return (
    <Ctx.Provider value={{ open, ask }}>
      {children}
      {req && (
        <Sheet label="Source" onClose={() => setReq(null)}>
          {req.note && <p className="mt-1 text-[13px] text-muted">{req.note}</p>}
          {!rows ? <p className="py-6 text-muted">Loading source…</p> : rows.map((r, i) => r ? (
            r.kind === "table" ? <TableView key={req.ids[i]} r={r} unit={req.unit} /> : <DocView key={req.ids[i]} r={r} />
          ) : <p key={req.ids[i]} className="mt-3 text-muted">Source for <span className="num">{req.ids[i]}</span> isn&apos;t available offline.</p>)}
          <button onClick={() => ask({ citation_id: docId })} className="mt-4 w-full rounded-lg border border-hairline py-2 text-[13px]">
            Ask FINN about this
          </button>
        </Sheet>
      )}
      {asking && <AskSheet symbol={symbol} name={payload.name} context={asking} onClose={() => setAsking(null)} onCite={open} />}
    </Ctx.Provider>
  );
}

export function Sheet({ label, onClose, children }: { label: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/30" onClick={onClose}>
      <div role="dialog" aria-modal aria-label={label} onClick={(e) => e.stopPropagation()}
        className="max-h-[80dvh] w-full max-w-[560px] overflow-y-auto rounded-t-2xl bg-raised px-4 pb-[calc(env(safe-area-inset-bottom)+1.25rem)] pt-3">
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-hairline" />
        <div className="flex items-center justify-between">
          <p className="text-[11px] uppercase tracking-wider text-muted">{label}</p>
          <button onClick={onClose} className="text-[13px] text-muted">Close</button>
        </div>
        {children}
      </div>
    </div>
  );
}

function TableView({ r, unit }: { r: TableReceipt; unit: string }) {
  return (
    <section className="mt-3">
      <p className="font-serif text-[16px]">{r.metric}</p>
      <p className="text-[12px] text-muted">{SECTION[r.section] ?? r.section}{r.basis ? ` · ${r.basis}` : ""} · screener.in</p>
      <div className="mt-2 overflow-x-auto">
        <table className="num w-full text-[12px]">
          <tbody>
            {r.periods.map((p, j) => (
              <tr key={p} className={j === r.highlight ? "bg-ink text-paper" : "border-b border-hairline"}>
                <td className="px-2 py-1">{periodLabel(p, r.section !== "quarters")}</td>
                <td className="px-2 py-1 text-right">{fmt(r.values[j], unit === "x" ? "₹ cr" : unit)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <a href={r.doc_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-[13px] font-medium underline underline-offset-2">
        Open on screener.in ↗
      </a>
    </section>
  );
}

const WINDOW = 700; // characters of context either side of the quote

function DocView({ r }: { r: DocReceipt }) {
  const [s, e] = r.highlight ?? [0, 0];
  const from = r.highlight ? Math.max(0, s - WINDOW) : 0;
  const to = r.highlight ? Math.min(r.text.length, e + WINDOW) : Math.min(r.text.length, WINDOW * 2);
  return (
    <section className="mt-3">
      <p className="font-serif text-[16px]">{r.kind === "transcript" ? `Earnings call · ${r.period}` : `Annual report ${r.period}`}</p>
      <p className="text-[12px] text-muted">{r.page ? <>Page <span className="num">{r.page}</span></> : null}{r.offline ? " · offline copy of the quote" : ""}</p>
      <blockquote className="mt-2 rounded-lg border border-hairline px-3 py-2 text-[13px] leading-relaxed">
        {from > 0 && "… "}
        {r.highlight ? <>
          {r.text.slice(from, s)}
          <mark className="bg-ink px-0.5 text-paper">{r.text.slice(s, e)}</mark>
          {r.text.slice(e, to)}
        </> : r.text.slice(from, to)}
        {to < r.text.length && " …"}
      </blockquote>
      {!r.highlight && <p className="mt-1 text-[12px] text-muted">The quote wasn&apos;t found word-for-word on this page; showing the page.</p>}
      {r.doc_url && (
        <a href={`${r.doc_url}${r.page ? `#page=${r.page}` : ""}`} target="_blank" rel="noreferrer"
          className="mt-2 inline-block text-[13px] font-medium underline underline-offset-2">Open the PDF at this page ↗</a>
      )}
    </section>
  );
}

/** A number you can tap for its source. */
export function Num({ cell, unit, className = "", note }: {
  cell: { value: number; citation?: string; citations?: string[]; derived?: string } | null | undefined;
  unit: string; className?: string; note?: string;
}) {
  const open = useReceipt();
  if (!cell) return <span className={`num ${className}`}>—</span>;
  const ids = cell.citation ? [cell.citation] : cell.citations ?? [];
  return (
    <button type="button" onClick={() => ids.length && open(ids, unit, note ?? (cell.derived ? `Computed: ${cell.derived}` : undefined))}
      className={`num underline decoration-hairline decoration-dotted underline-offset-4 hover:decoration-muted ${className}`}>
      {fmt(cell.value, unit)}
    </button>
  );
}

/** A small source chip for a claim: "p.14" for a document, "table" for a table row. */
export function Cite({ ids, unit = "", label, note }: { ids: (string | null | undefined)[]; unit?: string; label?: string; note?: string }) {
  const open = useReceipt();
  const clean = ids.filter((x): x is string => !!x);
  if (!clean.length) return null;
  const first = clean[0];
  const page = first.match(/-p(\d+)/)?.[1];
  const text = label ?? (first.startsWith("TBL-") ? "table" : page ? `p.${page}` : "source");
  return (
    <button type="button" onClick={() => open(clean, unit, note)}
      className="num ml-1 inline-block rounded border border-hairline px-1 align-[1px] text-[10px] leading-4 text-muted hover:text-ink">
      {text}
    </button>
  );
}
