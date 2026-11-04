import { periodLabel } from "@/lib/format";
import type { ResultsCard as RC } from "@/lib/types";

export const Chg = ({ v, unit = "%" }: { v: number | null | undefined; unit?: string }) => v === null || v === undefined
  ? <span className="num text-muted">—</span>
  : <span className={`chg ${v >= 0 ? "chg-up" : "chg-down"}`}><span aria-hidden className="text-[0.75em]">{v >= 0 ? "▲" : "▼"}</span>
    <span className="sr-only">{v >= 0 ? "up" : "down"}</span>{Math.abs(v).toFixed(unit === "%" ? 1 : 0)}{unit === "%" ? "%" : ` ${unit}`}</span>;

/** Headline numbers for the quarter vs last quarter and the same quarter last year. */
export function ResultsCard({ c }: { c: RC }) {
  return (
    <div className="mt-3">
      <div className="grid grid-cols-[minmax(0,1fr)_auto_4.9rem_4.9rem] items-center text-[13px]">
        <span className="whitespace-nowrap pb-1 text-[11px] text-muted">₹ cr · {periodLabel(c.period_end)}</span>
        <span className="pb-1 text-right text-[11px] text-muted">Quarter</span>
        <span className="pb-1 text-right text-[11px] text-muted">QoQ</span>
        <span className="pb-1 text-right text-[11px] text-muted">YoY</span>
        {c.rows.map((r) => (
          <div key={r.metric} className="contents">
            <span className="border-t border-hairline py-1.5">{r.metric}</span>
            <span className="num border-t border-hairline py-1.5 pl-2 text-right font-medium">
              {r.value_cr === null ? "—" : Math.round(r.value_cr).toLocaleString("en-IN")}</span>
            <span className="border-t border-hairline py-1.5 text-right text-[12px]"><Chg v={r.qoq_pct} /></span>
            <span className="border-t border-hairline py-1.5 text-right text-[12px]"><Chg v={r.yoy_pct} /></span>
          </div>
        ))}
      </div>
      {c.margin.ebitda_margin_pct !== undefined && (
        <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-muted">
          EBITDA margin <span className="num font-medium text-ink">{c.margin.ebitda_margin_pct}%</span>
          {c.margin.qoq_bps != null && <span className="inline-flex items-center gap-1"><Chg v={c.margin.qoq_bps} unit="bps" /> QoQ</span>}
          {c.margin.yoy_bps != null && <span className="inline-flex items-center gap-1"><Chg v={c.margin.yoy_bps} unit="bps" /> YoY</span>}
        </p>
      )}
      <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted">
        {c.verified
          ? <span className="chg chg-up py-px font-sans">✓ adds up</span>
          : <a href={c.url ?? "#"} target="_blank" rel="noreferrer" className="chg chg-down py-px font-sans">unverified — open filing</a>}
        <span>{c.source === "screener" ? "screener.in table" : c.source === "pdf" ? "results filing" : "XBRL"}{c.basis ? ` · ${c.basis}` : ""}</span>
      </p>
      {!c.verified && c.issues.length > 0 && <p className="mt-1 text-[11px] text-muted">{c.issues[0]}</p>}
      {c.ebitda_note && <p className="mt-1 text-[11px] leading-snug text-muted">{c.ebitda_note}</p>}
    </div>
  );
}
