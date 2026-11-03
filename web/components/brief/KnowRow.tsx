"use client";

import { useState } from "react";
import { CATEGORY_LABEL, when } from "@/lib/format";
import type { DigestCard } from "@/lib/types";

/** A Know item: one dense row; tap for the reasons and the filing. */
export function KnowRow({ c, now }: { c: DigestCard; now: string }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="border-b border-hairline last:border-b-0">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="grid w-full grid-cols-[4.75rem_1fr] gap-x-3 py-2.5 text-left">
        <span className="num pt-px text-[12px] font-medium">{c.symbol}</span>
        <span>
          <span className="line-clamp-2">{c.title}</span>
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
              <ul className="text-muted">
                {c.reasons.map((r) => <li key={r}>— {r}</li>)}
              </ul>
              {c.url && <a href={c.url} target="_blank" rel="noreferrer" className="mt-1.5 inline-block font-medium underline underline-offset-2">Open filing ↗</a>}
            </div>
          </div>
        </div>
      </div>
    </li>
  );
}
