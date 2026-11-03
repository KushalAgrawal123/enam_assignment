"use client";

import Link from "next/link";
import { useState } from "react";
import { dayMove, Sparkline } from "@/components/Sparkline";
import { Swipeable, TriageButtons } from "@/components/Swipeable";
import { CATEGORY_LABEL, pct, short, shortName, when } from "@/lib/format";
import type { Company, DigestCard, PricePoint } from "@/lib/types";
import { CardBody } from "./CardBody";

/** An Act item: the full card. Tap to see why it's here and everything folded into it. */
export function ActCard({ c, company, prices, now, onNoted, onSnooze }: {
  c: DigestCard; company?: Company; prices?: PricePoint[]; now: string; onNoted: () => void; onSnooze: () => void;
}) {
  const [open, setOpen] = useState(false);
  const move = dayMove(prices);
  return (
    <Swipeable onNoted={onNoted} onSnooze={onSnooze}>
    <article className="rounded-xl border border-hairline bg-raised">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="block w-full px-4 pb-3 pt-3.5 text-left">
        <div className="flex items-center gap-2 text-[12px] text-muted">
          <span aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
          <span className="num font-medium text-ink">{c.symbol}</span>
          <span className="truncate">{shortName(company?.name, c.symbol)}</span>
          <span className="num ml-auto shrink-0">{when(c.ts, now)}</span>
        </div>
        <h3 className="mt-1.5 font-serif text-[18px] leading-snug">{c.title}</h3>
        <CardBody c={c} />
        <div className="mt-2 flex items-center gap-3 text-[12px] text-muted">
          <span className="rounded border border-hairline px-1.5 py-px">{CATEGORY_LABEL[c.category] ?? c.category}</span>
          {c.attachments.length > 0 && <span>+{c.attachments.length} related</span>}
          <span className="ml-auto flex items-center gap-2">
            <Sparkline points={prices} />
            <span className="text-right leading-tight">
              <span className={`num block ${move === null ? "" : move >= 0 ? "text-up" : "text-down"}`}>{pct(move)}</span>
              <span className="block text-[10px]">last session</span>
            </span>
          </span>
        </div>
      </button>
      <div className="fold" data-open={open}>
        <div>
          <div className="border-t border-hairline px-4 pb-4 pt-3">
            <p className="text-[11px] uppercase tracking-wide text-muted">Why you&apos;re seeing this</p>
            <ul className="mt-1 space-y-0.5">
              {c.reasons.map((r) => <li key={r} className="before:mr-1.5 before:text-muted before:content-['—']">{r}</li>)}
            </ul>
            {c.attachments.length > 0 && (
              <>
                <p className="mt-3 text-[11px] uppercase tracking-wide text-muted">Folded in</p>
                <ul className="mt-1 space-y-1">
                  {[...c.attachments].sort((a, b) => (a.ts < b.ts ? -1 : 1)).map((a) => (
                    <li key={`${a.ts}${a.subject}`} className="flex gap-2">
                      <span className="num w-[4.5rem] shrink-0 text-[11px] leading-5 text-muted">{short(a.ts)}</span>
                      {a.url ? <a href={a.url} target="_blank" rel="noreferrer" className="line-clamp-2 underline decoration-hairline underline-offset-2">{a.subject}</a>
                        : <span className="line-clamp-2">{a.subject}</span>}
                    </li>
                  ))}
                </ul>
              </>
            )}
            <div className="mt-3 flex gap-4 text-[13px] font-medium">
              {c.url && <a href={c.url} target="_blank" rel="noreferrer" className="underline underline-offset-2">Open filing ↗</a>}
              <Link href={`/c/${c.symbol}#ledger`} className="underline underline-offset-2">Dig in →</Link>
            </div>
            <TriageButtons onNoted={onNoted} onSnooze={onSnooze} />
          </div>
        </div>
      </div>
    </article>
    </Swipeable>
  );
}
