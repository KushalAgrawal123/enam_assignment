"use client";

import type { ReactNode } from "react";
import { fmt, periodLabel } from "@/lib/format";
import type { Cell, Item, ResearchCard } from "@/lib/types";
import { MiniBars, MiniLine } from "./MiniCharts";
import { Num } from "./Receipt";

export function CardShell({ id, title, card, children }: { id: string; title: string; card?: ResearchCard; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24 rounded-xl border border-hairline bg-raised px-4 py-4">
      <h2 className="font-serif text-[19px]">{title}</h2>
      {!card ? <p className="mt-2 animate-pulse text-muted">Not built yet.</p>
        : card.status === "gap" || !card.data ? <GapNotice gaps={card.gaps} />
          : <>{children}{card.gaps.length > 0 && <p className="mt-3 text-[12px] text-muted">{card.gaps.join(" ")}</p>}</>}
    </section>
  );
}

export function GapNotice({ gaps }: { gaps: string[] }) {
  return <p className="mt-2 rounded-lg border border-dashed border-hairline px-3 py-2 text-[13px] text-muted">
    {gaps.length ? gaps.join(" ") : "Not enough source data to build this card."}</p>;
}

const tagText: Record<string, string> = { growing: "▲ growing", compressing: "▼ compressing", flat: "• flat" };
function Tag({ t, label }: { t: string | null | undefined; label: string }) {
  if (!t) return null;
  return <span className="rounded border border-hairline px-1.5 py-px text-[12px]">{label} {tagText[t]}</span>;
}

type Fin = { items: Item[]; quarterly_revenue: { period: string; value: number }[] };
export function FinancialsCard({ card }: { card?: ResearchCard }) {
  const d = card?.data as Fin | null;
  return (
    <CardShell id="financials" title="Financial snapshot" card={card}>
      {d && <>
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3">
          {d.items.map((i) => (
            <div key={i.label}>
              <dt className="text-[12px] text-muted">{i.label}</dt>
              <dd className="text-[17px]"><Num cell={i} unit={i.unit} /></dd>
              <dd className="num text-[11px] text-muted">{periodLabel(i.period, true)}</dd>
            </div>
          ))}
        </dl>
        {d.quarterly_revenue.length > 1 && <div className="mt-4">
          <p className="mb-1 text-[12px] text-muted">Revenue by quarter</p>
          <MiniBars points={d.quarterly_revenue} unit="₹ cr" annual={false} />
        </div>}
      </>}
    </CardShell>
  );
}

type Cagr = { value: number; years: number; citations: string[] } | null;
type Traj = {
  annual: { revenue: Cell[]; margin: Cell[]; net_profit: Cell[]; margin_label: string };
  cagr: Record<"revenue_3y" | "revenue_5y" | "net_profit_3y" | "net_profit_5y", Cagr>;
  last_8_quarters: { revenue: string | null; margin: string | null; net_profit: string | null };
};
export function TrajectoryCard({ card }: { card?: ResearchCard }) {
  const d = card?.data as Traj | null;
  const c = (x: Cagr, what: string) => x ? <Num cell={{ value: x.value, citations: x.citations }} unit="%"
    note={`${x.years}-year compound growth in ${what}, computed from the first and last year shown.`} /> : <span className="num">—</span>;
  return (
    <CardShell id="trajectory" title="Trajectory" card={card}>
      {d && <>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <Tag t={d.last_8_quarters.revenue} label="Revenue" />
          <Tag t={d.last_8_quarters.margin} label="Margin" />
          <Tag t={d.last_8_quarters.net_profit} label="Profit" />
        </div>
        <p className="mt-1 text-[11px] text-muted">Direction over the last 8 quarters.</p>
        <table className="mt-3 w-full text-[13px]">
          <thead><tr className="text-[11px] text-muted"><th className="text-left font-normal">CAGR</th><th className="text-right font-normal">3 yr</th><th className="text-right font-normal">5 yr</th></tr></thead>
          <tbody>
            <tr><td>Revenue</td><td className="text-right">{c(d.cagr.revenue_3y, "revenue")}</td><td className="text-right">{c(d.cagr.revenue_5y, "revenue")}</td></tr>
            <tr><td>Net profit</td><td className="text-right">{c(d.cagr.net_profit_3y, "net profit")}</td><td className="text-right">{c(d.cagr.net_profit_5y, "net profit")}</td></tr>
          </tbody>
        </table>
        <div className="mt-4"><p className="mb-1 text-[12px] text-muted">Revenue, yearly</p><MiniBars points={d.annual.revenue} unit="₹ cr" /></div>
        {d.annual.margin.length > 1 && <div className="mt-3">
          <p className="text-[12px] text-muted">{d.annual.margin_label}, yearly: <span className="num text-ink">
            {fmt(d.annual.margin[0].value, "%")} → {fmt(d.annual.margin.at(-1)!.value, "%")}</span></p>
          <MiniLine points={d.annual.margin} />
        </div>}
      </>}
    </CardShell>
  );
}

type Bal = { items: Item[]; working_capital: Record<string, Cell[]>; borrowings_5y: Cell[] };
const WC: Record<string, string> = { debtor_days: "Debtor days", inventory_days: "Inventory days", payable_days: "Payable days",
  cash_conversion_cycle: "Cash conversion cycle", working_capital_days: "Working-capital days" };
export function BalanceCard({ card }: { card?: ResearchCard }) {
  const d = card?.data as Bal | null;
  return (
    <CardShell id="balance_sheet" title="Balance sheet" card={card}>
      {d && <>
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3">
          {d.items.map((i) => (
            <div key={i.label}><dt className="text-[12px] text-muted">{i.label}</dt>
              <dd className="text-[16px]"><Num cell={i} unit={i.unit} /></dd></div>
          ))}
        </dl>
        {Object.keys(d.working_capital).length > 0 && (
          <table className="mt-4 w-full text-[13px]">
            <thead><tr className="text-[11px] text-muted"><th className="text-left font-normal">Working capital</th>
              {d.working_capital[Object.keys(d.working_capital)[0]].map((c) => <th key={c.period} className="num text-right font-normal">{periodLabel(c.period, true)}</th>)}</tr></thead>
            <tbody>{Object.entries(d.working_capital).map(([k, cells]) => (
              <tr key={k} className="border-t border-hairline"><td className="py-1">{WC[k] ?? k}</td>
                {cells.map((c) => <td key={c.period} className="text-right"><Num cell={c} unit="" /></td>)}</tr>
            ))}</tbody>
          </table>
        )}
      </>}
    </CardShell>
  );
}

type CashYear = { period: string; cfo: Cell; pat: Cell; cfo_pat: number | null; cfo_pat_citations: string[];
  fcf?: Cell & { label: string } };
type Cash = { years: CashYear[]; cfo_pat_avg_3y: number | null; flag: string | null };
export function CashCard({ card }: { card?: ResearchCard }) {
  const d = card?.data as Cash | null;
  return (
    <CardShell id="cash_quality" title="Cash quality" card={card}>
      {d && <>
        <p className="mt-2 text-[13px]">Do profits turn into cash? Operating cash flow ÷ net profit, 3-year average:{" "}
          <span className="num font-medium">{d.cfo_pat_avg_3y === null ? "—" : `${d.cfo_pat_avg_3y.toFixed(2)}×`}</span></p>
        {d.flag && <p className="mt-2 rounded-lg border border-down/40 px-3 py-2 text-[13px]">▼ {d.flag}</p>}
        <table className="mt-3 w-full text-[13px]">
          <thead><tr className="text-[11px] text-muted"><th className="text-left font-normal">Year</th><th className="text-right font-normal">Cash from ops</th>
            <th className="text-right font-normal">Net profit</th><th className="text-right font-normal">CFO/PAT</th><th className="text-right font-normal">FCF</th></tr></thead>
          <tbody>{d.years.map((y) => (
            <tr key={y.period} className="border-t border-hairline">
              <td className="num py-1">{periodLabel(y.period, true)}</td>
              <td className="text-right"><Num cell={y.cfo} unit="" /></td>
              <td className="text-right"><Num cell={y.pat} unit="" /></td>
              <td className="text-right">{y.cfo_pat === null ? "—" : <Num cell={{ value: y.cfo_pat, citations: y.cfo_pat_citations }} unit="x"
                note="Computed: cash from operating activity ÷ net profit, same year." />}</td>
              <td className="text-right">{y.fcf ? <Num cell={y.fcf} unit="" note={y.fcf.label} /> : "—"}</td>
            </tr>
          ))}</tbody>
        </table>
        <p className="mt-2 text-[11px] text-muted">₹ crore. Tap any number for its source.</p>
      </>}
    </CardShell>
  );
}
