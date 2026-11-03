import { periodLabel } from "@/lib/format";
import type { ResultsCard as RC } from "@/lib/types";

const chg = (v: number | null) => v === null ? <span className="text-muted">—</span>
  : <span className={v >= 0 ? "text-up" : "text-down"}>{v >= 0 ? "▲" : "▼"} {v > 0 ? "+" : ""}{v.toFixed(1)}%</span>;

/** Headline numbers for the quarter vs last quarter and the same quarter last year. */
export function ResultsCard({ c }: { c: RC }) {
  return (
    <div className="mt-3">
      <table className="num w-full text-[13px]">
        <thead>
          <tr className="text-[11px] text-muted">
            <th className="text-left font-normal">₹ crore · {periodLabel(c.period_end)}</th>
            <th className="text-right font-normal">Quarter</th>
            <th className="text-right font-normal">QoQ</th>
            <th className="text-right font-normal">YoY</th>
          </tr>
        </thead>
        <tbody>
          {c.rows.map((r) => (
            <tr key={r.metric} className="border-t border-hairline">
              <td className="py-1 font-sans">{r.metric}</td>
              <td className="text-right">{r.value_cr === null ? "—" : Math.round(r.value_cr).toLocaleString("en-IN")}</td>
              <td className="text-right">{chg(r.qoq_pct)}</td>
              <td className="text-right">{chg(r.yoy_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {c.margin.ebitda_margin_pct !== undefined && (
        <p className="mt-1.5 text-[12px] text-muted">EBITDA margin <span className="num text-ink">{c.margin.ebitda_margin_pct}%</span>
          {c.margin.qoq_bps != null && <>, <span className="num">{c.margin.qoq_bps > 0 ? "+" : ""}{c.margin.qoq_bps} bps</span> QoQ</>}
          {c.margin.yoy_bps != null && <>, <span className="num">{c.margin.yoy_bps > 0 ? "+" : ""}{c.margin.yoy_bps} bps</span> YoY</>}</p>
      )}
      <p className="mt-1.5 flex flex-wrap items-center gap-x-2 text-[11px] text-muted">
        {c.verified
          ? <span className="rounded border border-hairline px-1.5 py-px text-ink">✓ adds up</span>
          : <a href={c.url ?? "#"} target="_blank" rel="noreferrer" className="rounded border border-down/50 px-1.5 py-px text-down">unverified — open filing</a>}
        <span>source: {c.source === "screener" ? "screener.in table" : c.source === "pdf" ? "results filing" : "XBRL"}{c.basis ? ` · ${c.basis}` : ""}</span>
      </p>
      {!c.verified && c.issues.length > 0 && <p className="mt-1 text-[11px] text-muted">{c.issues[0]}</p>}
      {c.ebitda_note && <p className="mt-1 text-[11px] text-muted">{c.ebitda_note}</p>}
    </div>
  );
}
