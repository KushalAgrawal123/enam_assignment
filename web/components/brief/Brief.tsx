"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AlertCard } from "@/components/cards/AlertCard";
import { DataModeChip } from "@/components/DataModeChip";
import { WINDOW_HOURS, WindowChip, type WindowKey } from "@/components/WindowChip";
import { markAlertSeen } from "@/lib/api";
import { liveConfigured, loadBrief } from "@/lib/data";
import { hiddenIds, triage, undo } from "@/lib/triage";
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
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [lastAction, setLastAction] = useState<{ id: string; label: string } | null>(null);

  useEffect(() => { const t = setTimeout(() => setHidden(hiddenIds()), 0); return () => clearTimeout(t); }, []);
  const act = (id: string, action: "noted" | "snoozed", label: string, alertId?: number) => {
    triage(id, action);
    if (alertId !== undefined) markAlertSeen(alertId).catch(() => {});   // the server learns it was seen
    setHidden(hiddenIds());
    setLastAction({ id, label: action === "noted" ? `Noted: ${label}` : `Snoozed till 8am: ${label}` });
  };
  const undoLast = () => { if (lastAction) { undo(lastAction.id); setHidden(hiddenIds()); setLastAction(null); } };

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

  const digest = useMemo(() => {
    if (!data || !range) return null;
    const alerts = data.alerts.filter((a) => range.start <= a.ts && a.ts <= range.end && !hidden.has(`alert:${a.id}`));
    const d = buildDigest(data.filings, range.start, range.end, alerts);
    return { ...d, act: d.act.filter((c) => !hidden.has(c.id)), know: d.know.filter((c) => !hidden.has(c.id)) };
  }, [data, range, hidden]);

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
        <div className="flex shrink-0 items-center gap-2 pt-1">
          <DataModeChip mode={data.mode} freezeTime={data.freezeTime} reason={data.fallbackReason}
            liveAvailable={liveConfigured()} onToggle={toggleMode} />
          <Link href="/rules" aria-label="Your rules: what FINN alerts you about"
            className="grid h-7 w-7 place-items-center rounded-full border border-hairline text-[12px] text-muted hover:text-ink">⚙</Link>
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
        {digest.act.length === 0 && digest.alerts.length === 0 ? <p className="text-muted">Nothing needs action {WINDOW_LABEL[win]}.</p> : (
          <div className="space-y-3">
            {digest.alerts.map((a) => (
              <AlertCard key={`a${a.id}`} a={a} now={now}
                onNoted={() => act(`alert:${a.id}`, "noted", a.title, a.id)} onSnooze={() => act(`alert:${a.id}`, "snoozed", a.title)} />
            ))}
            {digest.act.map((c) => (
              <ActCard key={c.id} c={c} company={data.companies[c.symbol]} prices={data.prices[c.symbol]} now={now}
                onNoted={() => act(c.id, "noted", c.symbol)} onSnooze={() => act(c.id, "snoozed", c.symbol)} />
            ))}
          </div>
        )}
      </section>

      {digest.know.length > 0 && (
        <section className="mt-7" aria-labelledby="know-h">
          <h2 id="know-h" className="mb-1 text-[11px] uppercase tracking-wider text-muted">Know</h2>
          <ul>{digest.know.map((c) => <KnowRow key={c.id} c={c} now={now}
            onNoted={() => act(c.id, "noted", c.symbol)} onSnooze={() => act(c.id, "snoozed", c.symbol)} />)}</ul>
        </section>
      )}

      <RoutineFold routine={digest.routine} now={now} />
      <CaughtUp windowLabel={WINDOW_LABEL[win]} asOf={now} mode={data.mode} />
      {lastAction && (
        <div role="status" className="fixed inset-x-4 bottom-[calc(env(safe-area-inset-bottom)+4rem)] z-40 mx-auto flex max-w-[528px] items-center justify-between rounded-full bg-ink px-4 py-2 text-[13px] text-paper">
          <span className="truncate">{lastAction.label}</span>
          <button onClick={undoLast} className="ml-3 shrink-0 font-medium underline underline-offset-2">Undo</button>
        </div>
      )}
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
