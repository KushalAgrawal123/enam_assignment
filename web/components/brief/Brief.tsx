"use client";

import { useEffect, useMemo, useState } from "react";
import { DataModeChip } from "@/components/DataModeChip";
import { WINDOW_HOURS, WindowChip, type WindowKey } from "@/components/WindowChip";
import { liveConfigured, loadBrief } from "@/lib/data";
import { buildDigest } from "@/lib/digest";
import { istDay, longDay } from "@/lib/format";
import type { BriefData, DataMode } from "@/lib/types";
import { ActCard } from "./ActCard";
import { CaughtUp } from "./CaughtUp";
import { KnowRow } from "./KnowRow";
import { RoutineFold } from "./RoutineFold";

const MODE_KEY = "finn.mode";
const WINDOW_LABEL: Record<WindowKey, string> = { "24h": "in the last 24 hours", "3d": "in the last 3 days", "7d": "in the last 7 days", custom: "in this range" };

const z = (d: Date) => d.toISOString().replace(/\.\d{3}Z$/, "Z");
// IST calendar day -> UTC instant at its start / end.
const istStart = (day: string) => `${new Date(`${day}T00:00:00+05:30`).toISOString().replace(/\.\d{3}Z$/, "Z")}`;
const istEnd = (day: string) => `${new Date(`${day}T23:59:59+05:30`).toISOString().replace(/\.\d{3}Z$/, "Z")}`;

function readMode(): DataMode {
  try {
    return (localStorage.getItem(MODE_KEY) as DataMode) || "live";
  } catch {
    return "live";
  }
}

function plural(n: number, one: string, many = `${one}s`) {
  return `${n} ${n === 1 ? one : many}`;
}

export function Brief() {
  // null = use the saved preference (read inside the effect, so the server render never touches storage)
  const [prefer, setPrefer] = useState<DataMode | null>(null);
  const [data, setData] = useState<BriefData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [win, setWin] = useState<WindowKey>("24h");
  const [custom, setCustom] = useState({ from: "", to: "" });

  useEffect(() => {
    let alive = true;
    loadBrief(prefer ?? readMode()).then((d) => alive && (setData(d), setError(null))).catch((e) => alive && setError(String(e)));
    return () => { alive = false; };
  }, [prefer]);

  const range = useMemo(() => {
    if (!data) return null;
    if (win === "custom" && custom.from && custom.to) return { start: istStart(custom.from), end: istEnd(custom.to) };
    const hours = WINDOW_HOURS[win === "custom" ? "7d" : win];
    return { start: z(new Date(new Date(data.asOf).getTime() - hours * 3600 * 1000)), end: data.asOf };
  }, [data, win, custom]);

  const digest = useMemo(() => (data && range ? buildDigest(data.filings, range.start, range.end) : null), [data, range]);

  const toggleMode = () => {
    const next: DataMode = data?.mode === "live" ? "demo" : "live";
    try { localStorage.setItem(MODE_KEY, next); } catch { /* private mode: still switch for this visit */ }
    setData(null);
    setPrefer(next);
  };

  const pickWindow = (w: WindowKey) => {
    if (w === "custom" && data && !custom.from) {
      const end = istDay(data.asOf);
      setCustom({ from: istDay(z(new Date(new Date(data.asOf).getTime() - 2 * 86400 * 1000))), to: end });
    }
    setWin(w);
  };

  if (error) return <p className="mt-20 text-center text-muted">Couldn&apos;t load the brief: {error}</p>;
  if (!data || !digest || !range) return <BriefSkeleton />;

  const h = digest.headline;
  const now = data.asOf;
  return (
    <main>
      <header className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[12px] text-muted">{longDay(now)}</p>
          <h1 className="whitespace-nowrap font-serif text-[30px] leading-tight">Your brief</h1>
        </div>
        <div className="shrink-0 pt-1">
          <DataModeChip mode={data.mode} freezeTime={data.freezeTime} reason={data.fallbackReason}
            liveAvailable={liveConfigured()} onToggle={toggleMode} />
        </div>
      </header>

      <div className="mt-4">
        <WindowChip value={win} onChange={pickWindow} custom={custom} onCustom={setCustom} max={istDay(now)} />
      </div>

      <p className="mt-4 font-serif text-[17px] leading-snug" aria-live="polite">
        {h.filings === 0 ? <>No filings from your portfolio {WINDOW_LABEL[win]}.</> : <>
          <span className="text-accent">{h.act} to act on</span>, {h.know} worth knowing, {h.routine} routine
          <span className="text-muted"> — from {plural(h.filings, "filing")} across {plural(h.companies, "company", "companies")}.</span>
        </>}
      </p>

      <section className="mt-6" aria-labelledby="act-h">
        <h2 id="act-h" className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-wider text-muted">
          <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent" /> Act
        </h2>
        {digest.act.length === 0 ? <p className="text-muted">Nothing needs action {WINDOW_LABEL[win]}.</p> : (
          <div className="space-y-3">
            {digest.act.map((c) => (
              <ActCard key={c.id} c={c} company={data.companies[c.symbol]} prices={data.prices[c.symbol]} now={now} />
            ))}
          </div>
        )}
      </section>

      {digest.know.length > 0 && (
        <section className="mt-7" aria-labelledby="know-h">
          <h2 id="know-h" className="mb-1 text-[11px] uppercase tracking-wider text-muted">Know</h2>
          <ul>{digest.know.map((c) => <KnowRow key={c.id} c={c} now={now} />)}</ul>
        </section>
      )}

      <RoutineFold routine={digest.routine} now={now} />
      <CaughtUp windowLabel={WINDOW_LABEL[win]} asOf={now} mode={data.mode} />
    </main>
  );
}

function BriefSkeleton() {
  return (
    <main aria-busy className="animate-pulse">
      <div className="h-3 w-32 rounded bg-hairline" />
      <div className="mt-2 h-8 w-40 rounded bg-hairline" />
      <div className="mt-5 h-7 w-56 rounded-full bg-hairline" />
      <div className="mt-5 h-5 w-full rounded bg-hairline" />
      {[0, 1, 2].map((i) => <div key={i} className="mt-4 h-28 rounded-xl bg-hairline" />)}
    </main>
  );
}
