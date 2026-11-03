"use client";

import { short } from "@/lib/format";
import type { DataMode } from "@/lib/types";

/** "Live" or "Demo data · as of …". Tapping switches mode; a fallback explains itself on long-press/hover. */
export function DataModeChip({ mode, freezeTime, reason, liveAvailable, onToggle }: {
  mode: DataMode; freezeTime: string | null; reason: string | null; liveAvailable: boolean; onToggle: () => void;
}) {
  const label = mode === "live" ? "Live" : `Demo · ${freezeTime ? short(freezeTime) : "—"}`;
  const title = mode === "live"
    ? "Live data from the exchange feed. Tap to view the demo snapshot."
    : reason ? `Showing the demo snapshot because: ${reason}.${liveAvailable ? " Tap to retry live." : ""}`
      : "Showing the frozen demo snapshot. Tap for live data.";
  return (
    <button onClick={onToggle} title={title} aria-label={title}
      className="num inline-flex items-center gap-1.5 rounded-full border border-hairline px-2.5 py-1 text-[11px] text-muted hover:text-ink">
      <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${mode === "live" ? "bg-up" : "bg-muted"}`} />
      {label}
    </button>
  );
}
