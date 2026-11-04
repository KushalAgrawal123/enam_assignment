"use client";

import { useState } from "react";
import { TriageButtons } from "@/components/Swipeable";
import { when } from "@/lib/format";
import type { Alert, AlertPayload } from "@/lib/types";

/** A triggered alert at the top of Act: what crossed which of your thresholds, and the likely cause. */
export function AlertCard({ a, now, onNoted, onSnooze }: { a: Alert; now: string; onNoted: () => void; onSnooze: () => void }) {
  const [open, setOpen] = useState(false);
  const p = a.payload as unknown as AlertPayload;
  return (
    <article className="rounded-xl border border-accent/40 bg-raised">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="block w-full px-4 py-3 text-left">
        <div className="flex items-center gap-2 text-[12px] text-muted">
          <span aria-hidden className="text-accent">◆</span>
          <span className="font-medium text-ink">{a.kind === "price_volume" ? "Unusual move" : "Alert"}</span>
          <span className="num ml-auto">{when(a.ts, now)}</span>
        </div>
        <h3 className="mt-1.5 font-serif text-[18px] leading-snug">{a.title}</h3>
        <p className="mt-0.5 line-clamp-2 text-[12px] text-muted">
          {p?.likely_cause ? <>Likely cause: {p.likely_cause.subject}</> : a.kind === "price_volume" ? "No filing from the company in the 24 hours before the close." : null}
        </p>
      </button>
      <div className="fold" data-open={open}><div>
        <div className="border-t border-hairline px-4 pb-4 pt-3 text-[13px]">
          <ul>{a.reasons.map((r) => <li key={r}>— {r}</li>)}</ul>
          {p?.index_ret_pct != null && <p className="mt-1 text-[12px] text-muted">NIFTY 50 that day: <span className="num">{p.index_ret_pct > 0 ? "+" : ""}{p.index_ret_pct.toFixed(1)}%</span></p>}
          {(p?.likely_cause?.url || p?.url) && <a href={(p.likely_cause?.url ?? p.url)!} target="_blank" rel="noreferrer" className="mt-2 inline-block font-medium underline underline-offset-2">Open filing ↗</a>}
          <TriageButtons onNoted={onNoted} onSnooze={onSnooze} />
        </div>
      </div></div>
    </article>
  );
}
