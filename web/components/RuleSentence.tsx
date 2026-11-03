"use client";

import { useState } from "react";

/** A number inside a sentence, edited in place. Commits on blur or Enter; Escape reverts. */
export function InlineNumber({ value, onCommit, min, max, suffix = "", label }: {
  value: number; onCommit: (v: number) => void; min: number; max: number; suffix?: string; label: string;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const commit = () => {
    if (draft === null) return;
    const v = Number(draft);
    setDraft(null);
    if (Number.isFinite(v) && v >= min && v <= max && v !== value) onCommit(v);
  };
  return (
    <span className="inline-flex items-baseline">
      <input aria-label={label} inputMode="decimal" value={draft ?? String(value)} onChange={(e) => setDraft(e.target.value)}
        onBlur={commit} onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); if (e.key === "Escape") setDraft(null); }}
        style={{ width: `${Math.max(2, (draft ?? String(value)).length) + 0.5}ch` }}
        className="num border-b border-dashed border-ink bg-transparent px-0.5 text-center text-ink outline-none focus:border-solid" />
      {suffix && <span className="num">{suffix}</span>}
    </span>
  );
}
