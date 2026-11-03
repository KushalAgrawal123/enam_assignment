"use client";

import Link from "next/link";
import { useState } from "react";
import { Swipeable, TriageButtons } from "@/components/Swipeable";
import { CATEGORY_LABEL, when } from "@/lib/format";
import type { DigestCard, PushCard } from "@/lib/types";
import { CardBody } from "./CardBody";

/** A Know item: one dense row; tap for the reasons and the filing. */
export function KnowRow({ c, now, onNoted, onSnooze }: { c: DigestCard; now: string; onNoted: () => void; onSnooze: () => void }) {
  const [open, setOpen] = useState(false);
  const card = c.card as PushCard | null;
  const line = card?.type === "oneliner" ? card.line : null;
  return (
    <li className="border-b border-hairline last:border-b-0">
      <Swipeable onNoted={onNoted} onSnooze={onSnooze}>
      <div className="bg-paper">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="grid w-full grid-cols-[4.75rem_1fr] gap-x-3 py-2.5 text-left">
        <span className="num pt-px text-[12px] font-medium">{c.symbol}</span>
        <span>
          <span className="line-clamp-2">{line ?? c.title}</span>
          <span className="mt-0.5 block text-[12px] text-muted">
            {CATEGORY_LABEL[c.category] ?? c.category} · <span className="num">{when(c.ts, now)}</span>
            {c.attachments.length > 0 && <> · +{c.attachments.length}</>}
          </span>
        </span>
      </button>
      <div className="fold" data-open={open}>
        <div>
          <div className="grid grid-cols-[4.75rem_1fr] gap-x-3 pb-3">
            <span />
            <div className="text-[13px]">
              {card && card.type !== "oneliner" && <CardBody c={c} />}
              {line && <p className="mb-1 text-muted">Filing: {c.title}</p>}
              <ul className="text-muted">
                {c.reasons.map((r) => <li key={r}>— {r}</li>)}
              </ul>
              <div className="mt-1.5 flex gap-4 font-medium">
                {c.url && <a href={c.url} target="_blank" rel="noreferrer" className="underline underline-offset-2">Open filing ↗</a>}
                <Link href={`/c/${c.symbol}#ledger`} className="underline underline-offset-2">Dig in →</Link>
              </div>
              <TriageButtons onNoted={onNoted} onSnooze={onSnooze} />
            </div>
          </div>
        </div>
      </div>
      </div>
      </Swipeable>
    </li>
  );
}
