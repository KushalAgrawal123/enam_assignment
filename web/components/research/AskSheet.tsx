"use client";

import { useState } from "react";
import { askFinn } from "@/lib/api";
import type { AskAnswer } from "@/lib/types";
import { Sheet } from "./Receipt";

const SUGGESTIONS = ["What did management guide for margins?", "What did they say about demand?", "How is working capital moving?"];

/** Ask FINN: answers only from this company's own calls, annual report and tables, with sources. */
export function AskSheet({ symbol, name, context, onClose, onCite }: {
  symbol: string; name: string; context: { card?: string; citation_id?: string }; onClose: () => void;
  onCite: (ids: string[], unit: string, note?: string) => void;
}) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<AskAnswer | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function go(question: string) {
    if (!question.trim()) return;
    setQ(question);
    setBusy(true); setErr(null); setRes(null);
    try { setRes(await askFinn(symbol, question, context)); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  return (
    <Sheet label={`Ask FINN · ${symbol}`} onClose={onClose}>
      <p className="mt-1 text-[12px] text-muted">Answers come only from {name}&apos;s own calls, annual report and tables.</p>
      <form onSubmit={(e) => { e.preventDefault(); go(q); }} className="mt-3 flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} maxLength={500} autoFocus placeholder="Ask a question"
          className="min-w-0 flex-1 rounded-lg border border-hairline bg-paper px-3 py-2 text-[16px] outline-none focus:border-muted" />
        <button disabled={busy || !q.trim()} className="rounded-lg bg-ink px-3 text-[13px] text-paper disabled:opacity-40">Ask</button>
      </form>
      {!res && !busy && !err && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((s) => <button key={s} onClick={() => go(s)} className="rounded-full border border-hairline px-3 py-1 text-[12px] text-muted">{s}</button>)}
        </div>
      )}
      {busy && <p className="py-6 text-muted">Reading the sources…</p>}
      {err && <p className="mt-3 text-[13px] text-muted">{err}</p>}
      {res && (
        <div className="mt-3">
          <p className={`text-[14px] leading-relaxed ${res.not_found ? "text-muted" : ""}`}>{res.answer}</p>
          {res.citations.length > 0 && (
            <ul className="mt-2 space-y-1 text-[12px]">
              {res.citations.map((c) => (
                <li key={c.id}>
                  <button onClick={() => onCite([c.id], c.table_ref?.metric.includes("%") ? "%" : "₹ cr")} className="text-left underline decoration-hairline underline-offset-2">
                    {c.kind === "table" ? `${c.table_ref?.metric} · ${c.table_ref?.period}` : `${c.kind === "transcript" ? "Call" : "Annual report"} ${c.period} · page ${c.page}`}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {res.method === "rules" && !res.not_found && <p className="mt-2 text-[11px] text-muted">Quoted verbatim from the best-matching passages.</p>}
        </div>
      )}
    </Sheet>
  );
}
