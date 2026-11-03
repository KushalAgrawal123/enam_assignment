"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

type Row = [symbol: string, name: string];
const RECENT = "finn.recent";

function readRecent(): string[] {
  try { return JSON.parse(localStorage.getItem(RECENT) ?? "[]"); } catch { return []; }
}

/** Command bar over every NSE equity. Symbol prefix matches rank first, then company-name matches. */
export function LookUp() {
  const router = useRouter();
  const [all, setAll] = useState<Row[]>([]);
  const [q, setQ] = useState("");
  const [recent, setRecent] = useState<string[]>([]);

  useEffect(() => {
    fetch("/nse-symbols.json").then((r) => r.json()).then(setAll).catch(() => {});
    const t = setTimeout(() => setRecent(readRecent()), 0);
    return () => clearTimeout(t);
  }, []);

  const hits = useMemo(() => {
    const s = q.trim().toUpperCase();
    if (!s) return [];
    const pre = all.filter(([sym]) => sym.startsWith(s));
    const name = all.filter(([sym, n]) => !sym.startsWith(s) && n.toUpperCase().includes(s));
    return [...pre.sort((a, b) => a[0].length - b[0].length), ...name].slice(0, 12);
  }, [q, all]);

  const go = (sym: string) => {
    const next = [sym, ...readRecent().filter((x) => x !== sym)].slice(0, 6);
    try { localStorage.setItem(RECENT, JSON.stringify(next)); } catch { /* fine */ }
    router.push(`/c/${encodeURIComponent(sym)}`);
  };
  const names = useMemo(() => Object.fromEntries(all), [all]);

  return (
    <main>
      <h1 className="font-serif text-[30px] leading-tight">Look up</h1>
      <p className="text-[13px] text-muted">Any NSE company: numbers from its filings, every figure tappable to its source.</p>
      <form className="mt-4" onSubmit={(e) => { e.preventDefault(); const s = hits[0]?.[0] ?? q.trim().toUpperCase(); if (s) go(s); }}>
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Symbol or company, e.g. ASIANPAINT"
          aria-label="Search NSE companies" autoCapitalize="characters" autoCorrect="off" spellCheck={false}
          className="w-full rounded-xl border border-hairline bg-raised px-4 py-3 text-[16px] outline-none focus:border-muted" />
      </form>
      <ul className="mt-2">
        {hits.map(([sym, n]) => (
          <li key={sym}><button onClick={() => go(sym)} className="grid w-full grid-cols-[6.5rem_1fr] gap-3 border-b border-hairline py-2.5 text-left">
            <span className="num text-[13px] font-medium">{sym}</span><span className="truncate text-muted">{n}</span></button></li>
        ))}
        {q && all.length > 0 && hits.length === 0 && <li className="py-3 text-muted">No NSE company matches “{q}”.</li>}
      </ul>
      {!q && recent.length > 0 && (
        <section className="mt-6">
          <h2 className="text-[11px] uppercase tracking-wider text-muted">Recent</h2>
          <ul className="mt-1">{recent.map((sym) => (
            <li key={sym}><button onClick={() => go(sym)} className="grid w-full grid-cols-[6.5rem_1fr] gap-3 border-b border-hairline py-2.5 text-left">
              <span className="num text-[13px] font-medium">{sym}</span><span className="truncate text-muted">{names[sym] ?? ""}</span></button></li>
          ))}</ul>
        </section>
      )}
      {!q && (
        <section className="mt-6">
          <h2 className="text-[11px] uppercase tracking-wider text-muted">Research set</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            {["BEL", "POLYCAB", "PERSISTENT", "KPITTECH", "HCLTECH"].map((s) => (
              <button key={s} onClick={() => go(s)} className="num rounded-full border border-hairline px-3 py-1 text-[12px]">{s}</button>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
