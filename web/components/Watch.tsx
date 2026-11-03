"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { dayMove, Sparkline } from "@/components/Sparkline";
import { getSettings } from "@/lib/api";
import { loadBrief } from "@/lib/data";
import { pct, shortName } from "@/lib/format";
import { hiddenIds } from "@/lib/triage";
import type { BriefData, PricePoint, ResultsCard, Settings } from "@/lib/types";

const DEFAULTS = { vol_multiple: 2, vol_lookback: 20, price_move_pct: 5 } as Pick<Settings, "vol_multiple" | "vol_lookback" | "price_move_pct">;
const WEEK = 7 * 86400 * 1000;

type Row = {
  symbol: string; name: string; prices?: PricePoint[]; move: number | null; act: number; alerts: number;
  volX: number | null; nearness: number; results: { pat_yoy: number | null; verified: boolean; period: string } | null; score: number;
};

function volMultiple(p: PricePoint[] | undefined, lookback: number): number | null {
  if (!p || p.length < 3) return null;
  const last = p.at(-1)!;
  const hist = p.slice(-1 - lookback, -1).map((x) => x.volume).filter((v): v is number => !!v);
  if (!last.volume || !hist.length) return null;
  return last.volume / (hist.reduce((a, b) => a + b, 0) / hist.length);
}

/** The portfolio sorted by what needs attention: open Act items, alerts, closeness to your thresholds, last results. */
export function Watch({ initial = null }: { initial?: BriefData | null }) {
  const [data, setData] = useState<BriefData | null>(initial);
  const [rules, setRules] = useState(DEFAULTS);
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  useEffect(() => {
    let alive = true;
    let mode: "live" | "demo" = "live";
    try { mode = (localStorage.getItem("finn.mode") as "live" | "demo") || "live"; } catch { /* default */ }
    if (!(initial && mode === "live")) loadBrief(mode).then((d) => alive && setData(d));
    getSettings().then((s) => alive && setRules({ vol_multiple: s.vol_multiple, vol_lookback: s.vol_lookback, price_move_pct: s.price_move_pct })).catch(() => {});
    const t = setTimeout(() => setHidden(hiddenIds()), 0);
    return () => { alive = false; clearTimeout(t); };
  }, [initial]);

  const rows = useMemo<Row[]>(() => {
    if (!data) return [];
    const since = new Date(new Date(data.asOf).getTime() - WEEK).toISOString();
    return Object.values(data.companies).filter((c) => c.in_portfolio).map((c) => {
      const fs = data.filings.filter((f) => f.symbol === c.symbol);
      const act = fs.filter((f) => f.tier === "act" && f.ts >= since && !hidden.has(f.id)).length;
      const alerts = data.alerts.filter((a) => a.symbol === c.symbol && a.ts >= since && !a.seen && !hidden.has(`alert:${a.id}`)).length;
      const prices = data.prices[c.symbol];
      const move = dayMove(prices);
      const volX = volMultiple(prices, rules.vol_lookback);
      const nearness = Math.min(1, Math.max(volX ? volX / rules.vol_multiple : 0, move !== null ? Math.abs(move) / rules.price_move_pct : 0));
      const r = fs.find((f) => (f.card as ResultsCard | null)?.type === "results")?.card as ResultsCard | undefined;
      const results = r ? { pat_yoy: r.rows.find((x) => x.metric === "PAT")?.yoy_pct ?? null, verified: r.verified, period: r.period_end } : null;
      const score = act * 3 + alerts * 2 + nearness + (results && results.pat_yoy !== null && results.pat_yoy < 0 ? 0.5 : 0);
      return { symbol: c.symbol, name: c.name, prices, move, act, alerts, volX, nearness, results, score };
    }).sort((a, b) => b.score - a.score || a.symbol.localeCompare(b.symbol));
  }, [data, rules, hidden]);

  if (!data) return (
    <main aria-busy><h1 className="font-serif text-[30px]">Watch</h1>
      <div className="mt-4 animate-pulse space-y-2">{[0, 1, 2, 3, 4].map((i) => <div key={i} className="h-14 rounded-lg bg-hairline" />)}</div></main>
  );

  return (
    <main>
      <h1 className="font-serif text-[30px] leading-tight">Watch</h1>
      <p className="mt-1 text-[12px] text-muted">
        Your <span className="num">{rows.length}</span> holdings, most in need of attention first: open Act items, unseen alerts,
        how close today is to your thresholds (<span className="num">{rules.vol_multiple}×</span> volume, <span className="num">±{rules.price_move_pct}%</span>), and the last results.
        {data.mode === "demo" && " Demo data."}
      </p>
      {rows.length === 0 ? <p className="mt-8 text-center text-muted">No portfolio companies are set up yet.</p> : (
        <ul className="mt-4 divide-y divide-hairline border-y border-hairline">
          {rows.map((r) => (
            <li key={r.symbol}>
              <Link href={`/c/${r.symbol}`} className="flex items-center gap-3 py-2.5">
                <div className="min-w-0 flex-1">
                  <p className="flex items-baseline gap-2"><span className="num text-[13px] font-medium">{r.symbol}</span>
                    <span className="truncate text-[12px] text-muted">{shortName(r.name, r.symbol)}</span></p>
                  <p className="mt-0.5 flex flex-wrap gap-1.5 text-[11px]">
                    {r.act > 0 && <span className="rounded border border-accent/50 px-1 text-accent">{r.act} to act</span>}
                    {r.alerts > 0 && <span className="rounded border border-accent/50 px-1 text-accent">{r.alerts} alert{r.alerts > 1 ? "s" : ""}</span>}
                    {r.volX !== null && <span className={`num rounded border px-1 ${r.volX >= rules.vol_multiple ? "border-ink" : "border-hairline text-muted"}`}>vol {r.volX.toFixed(1)}×</span>}
                    {r.results && <span className="num rounded border border-hairline px-1 text-muted">
                      results PAT {pct(r.results.pat_yoy)} YoY{r.results.verified ? " ✓" : ""}</span>}
                    {r.act === 0 && r.alerts === 0 && !r.results && r.nearness < 0.5 && <span className="text-muted">quiet</span>}
                  </p>
                </div>
                <Sparkline points={r.prices} />
                <span className={`num w-16 text-right text-[12px] ${r.move === null ? "text-muted" : r.move >= 0 ? "text-up" : "text-down"}`}>
                  {pct(r.move)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
