"use client";

import { useState } from "react";
import { when } from "@/lib/format";
import type { Digest } from "@/lib/types";

/** Routine paperwork, collapsed to one line. It's all still here, just out of the way. */
export function RoutineFold({ routine, now }: { routine: Digest["routine"]; now: string }) {
  const [open, setOpen] = useState(false);
  if (!routine.count) return null;
  return (
    <section id="routine" className="mt-6 scroll-mt-4">
      <button onClick={() => setOpen(!open)} aria-expanded={open}
        className="flex w-full items-center justify-between border-y border-hairline py-3 text-left text-muted">
        <span>
          <span className="num text-ink">{routine.count}</span> routine filing{routine.count > 1 ? "s" : ""} from{" "}
          <span className="num text-ink">{routine.companies}</span> compan{routine.companies > 1 ? "ies" : "y"}
        </span>
        <span aria-hidden className={`transition-transform duration-150 ${open ? "rotate-180" : ""}`}>⌄</span>
      </button>
      <div className="fold" data-open={open}>
        <div>
          <dl className="space-y-3 pt-3 text-[13px]">
            {Object.entries(routine.by_company).map(([sym, items]) => (
              <div key={sym} className="grid grid-cols-[4.75rem_1fr] gap-x-3">
                <dt className="num text-[12px] font-medium">{sym}</dt>
                <dd className="space-y-1">
                  {items.map((i) => (
                    <div key={i.ts + i.title} className="flex gap-2 text-muted">
                      {i.url ? <a href={i.url} target="_blank" rel="noreferrer" className="hover:text-ink">{i.title}</a> : <span>{i.title}</span>}
                      <span className="num ml-auto shrink-0 text-[11px]">{when(i.ts, now)}</span>
                    </div>
                  ))}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </section>
  );
}
