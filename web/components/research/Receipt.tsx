"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { tableReceipt } from "@/lib/api";
import { fmt, periodLabel } from "@/lib/format";
import type { ResearchPayload, TableReceipt } from "@/lib/types";

// Every number has a receipt: tap it and the sheet shows the source row with the cited cell marked.
type Open = (citationIds: string[], unit: string, note?: string) => void;
const Ctx = createContext<Open>(() => {});
export const useReceipt = () => useContext(Ctx);

const SECTION = { "profit-loss": "Profit & loss (annual)", quarters: "Quarterly results", "balance-sheet": "Balance sheet",
  "cash-flow": "Cash flow", ratios: "Ratios", "Key ratios": "Key ratios" } as Record<string, string>;

export function ReceiptProvider({ symbol, payload, children }: { symbol: string; payload: ResearchPayload; children: ReactNode }) {
  const [req, setReq] = useState<{ ids: string[]; unit: string; note?: string } | null>(null);
  const [rows, setRows] = useState<(TableReceipt | null)[] | null>(null);
  const open: Open = useCallback((ids, unit, note) => { setRows(null); setReq({ ids, unit, note }); }, []);

  useEffect(() => {
    if (!req) return;
    let alive = true;
    Promise.all(req.ids.map((id) => tableReceipt(symbol, id, payload))).then((r) => alive && setRows(r));
    return () => { alive = false; };
  }, [req, symbol, payload]);

  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setReq(null);
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, []);

  return (
    <Ctx.Provider value={open}>
      {children}
      {req && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/30" onClick={() => setReq(null)}>
          <div role="dialog" aria-modal aria-label="Source" onClick={(e) => e.stopPropagation()}
            className="max-h-[75dvh] w-full max-w-[560px] overflow-y-auto rounded-t-2xl bg-raised px-4 pb-[calc(env(safe-area-inset-bottom)+1.25rem)] pt-3">
            <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-hairline" />
            <div className="flex items-center justify-between">
              <p className="text-[11px] uppercase tracking-wider text-muted">Receipt</p>
              <button onClick={() => setReq(null)} className="text-[13px] text-muted">Close</button>
            </div>
            {req.note && <p className="mt-1 text-[13px] text-muted">{req.note}</p>}
            {!rows ? <p className="py-6 text-muted">Loading source…</p> : rows.map((r, i) => r ? (
              <section key={req.ids[i]} className="mt-3">
                <p className="font-serif text-[16px]">{r.metric}</p>
                <p className="text-[12px] text-muted">{SECTION[r.section] ?? r.section}{r.basis ? ` · ${r.basis}` : ""} · screener.in</p>
                <div className="mt-2 overflow-x-auto">
                  <table className="num w-full text-[12px]">
                    <tbody>
                      {r.periods.map((p, j) => (
                        <tr key={p} className={j === r.highlight ? "bg-ink text-paper" : "border-b border-hairline"}>
                          <td className="px-2 py-1">{periodLabel(p, r.section !== "quarters")}</td>
                          <td className="px-2 py-1 text-right">{fmt(r.values[j], req.unit === "x" ? "₹ cr" : req.unit)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <a href={r.doc_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-[13px] font-medium underline underline-offset-2">
                  Open on screener.in ↗
                </a>
              </section>
            ) : <p key={req.ids[i]} className="mt-3 text-muted">Source for {req.ids[i]} isn&apos;t available offline.</p>)}
          </div>
        </div>
      )}
    </Ctx.Provider>
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
