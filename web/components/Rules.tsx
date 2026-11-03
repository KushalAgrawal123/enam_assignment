"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { InlineNumber } from "@/components/RuleSentence";
import { getSettings, putSettings } from "@/lib/api";
import { routineCategories, undoRoutine } from "@/lib/feedback";
import { CATEGORY_LABEL } from "@/lib/format";
import type { Settings } from "@/lib/types";

const CATS: [string, string][] = [["results", "results"], ["M&A", "deals"], ["management_change", "management changes"],
  ["litigation", "legal & regulatory action"], ["pledging", "promoter pledges"], ["credit_rating", "credit ratings"],
  ["fund_raise", "fund raises"], ["capex", "capex"], ["insider_trading", "insider trades"], ["dividend", "dividends"]];

/** The investor owns the filter: every threshold is a sentence you can edit. */
export function Rules() {
  const [s, setS] = useState<Settings | null>(null);
  const [status, setStatus] = useState<string>("");
  const [routine, setRoutine] = useState<string[]>([]);
  useEffect(() => { getSettings().then(setS).catch((e) => setStatus(`Couldn't load your rules: ${e.message}`)); }, []);
  useEffect(() => { const t = setTimeout(() => setRoutine([...routineCategories()]), 0); return () => clearTimeout(t); }, []);

  const unroutine = (c: string) => {
    undoRoutine(c);
    setRoutine(routine.filter((x) => x !== c));
    if (s?.weights && c in s.weights) {
      const w = { ...s.weights };
      delete w[c];
      save({ weights: w });
    }
  };

  const save = (patch: Partial<Settings>) => {
    if (!s) return;
    const prev = s;
    setS({ ...s, ...patch });
    setStatus("Saving…");
    putSettings(patch).then((n) => { setS(n); setStatus("Saved. Applies from the next check."); })
      .catch((e) => { setS(prev); setStatus(`Not saved: ${e.message}`); });
  };
  const toggleCat = (c: string) => {
    if (!s) return;
    const has = s.alert_categories.includes(c);
    save({ alert_categories: has ? s.alert_categories.filter((x) => x !== c) : [...s.alert_categories, c] });
  };

  return (
    <main>
      <Link href="/" className="text-[12px] text-muted">← Brief</Link>
      <h1 className="mt-1 font-serif text-[30px] leading-tight">Your rules</h1>
      <p className="text-[13px] text-muted">What counts as unusual is your call. Tap a number to change it.</p>
      {!s ? <p className="mt-8 text-muted">{status || "Loading…"}</p> : (
        <div className="mt-6 space-y-6 font-serif text-[19px] leading-relaxed">
          <p>Tell me when a stock trades more than{" "}
            <InlineNumber label="Volume multiple" value={Number(s.vol_multiple)} min={1} max={20} suffix="×"
              onCommit={(v) => save({ vol_multiple: v })} /> its{" "}
            <InlineNumber label="Lookback sessions" value={Number(s.vol_lookback)} min={5} max={120}
              onCommit={(v) => save({ vol_lookback: v })} />-day average volume,
            <span className="text-muted"> ignoring stocks that average under{" "}
              <InlineNumber label="Minimum average volume" value={Number(s.min_avg_volume)} min={0} max={1e9}
                onCommit={(v) => save({ min_avg_volume: v })} /> shares a day.</span>
          </p>
          <p>…or when it moves more than ±
            <InlineNumber label="Price move percent" value={Number(s.price_move_pct)} min={0.5} max={50} suffix="%"
              onCommit={(v) => save({ price_move_pct: v })} /> in a day,{" "}
            <button onClick={() => save({ relative_to_index: !s.relative_to_index })}
              className="border-b border-dashed border-ink" aria-pressed={s.relative_to_index}>
              {s.relative_to_index ? "measured against NIFTY 50" : "on its own"}</button>
            <span className="text-muted">{s.relative_to_index ? " (so a market-wide fall doesn't alert on every stock)." : "."}</span>
          </p>
          <div>
            <p>Alert me the moment a company files about</p>
            <div className="mt-2 flex flex-wrap gap-1.5 font-sans text-[13px]">
              {CATS.map(([c, label]) => {
                const on = s.alert_categories.includes(c);
                return <button key={c} onClick={() => toggleCat(c)} aria-pressed={on}
                  className={`rounded-full border px-3 py-1 ${on ? "border-ink bg-ink text-paper" : "border-hairline text-muted"}`}>{label}</button>;
              })}
            </div>
            <p className="mt-3">…when FINN ranks it{" "}
              <button onClick={() => save({ min_category_tier: s.min_category_tier === "act" ? "know" : "act" })}
                className="border-b border-dashed border-ink">{s.min_category_tier === "act" ? "Act" : "Know or higher"}</button>.
            </p>
          </div>
        </div>
      )}
      {routine.length > 0 && (
        <div className="mt-6 font-serif text-[19px] leading-relaxed">
          <p>Treat these as routine, because you kept marking them Noted:</p>
          <div className="mt-2 flex flex-wrap gap-1.5 font-sans text-[13px]">
            {routine.map((c) => <button key={c} onClick={() => unroutine(c)} className="rounded-full border border-ink px-3 py-1">
              {CATEGORY_LABEL[c] ?? c} <span aria-hidden>×</span><span className="sr-only">: show again</span></button>)}
          </div>
        </div>
      )}
      <p className="mt-8 text-[12px] text-muted" aria-live="polite">{status}</p>
      <p className="mt-2 text-[12px] text-muted">Alerts appear at the top of your brief, and on Telegram once a bot is connected. Prices are checked after the close (17:30 IST); filings every 15 minutes.</p>
    </main>
  );
}
