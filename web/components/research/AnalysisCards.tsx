"use client";

import type {
  BullBearData, GuidanceData, LedgerData, LedgerItem, LedgerVerdict, Method, NarrativeData, ResearchCard, SnapshotData, Target, VerdictData,
} from "@/lib/types";
import { CardShell } from "./NumberCards";
import { Cite, useAsk } from "./Receipt";

const VERDICT: Record<LedgerVerdict, { label: string; mark: string; cls: string }> = {
  delivered: { label: "Delivered", mark: "✓", cls: "text-up border-up/40" },
  beat: { label: "Beat", mark: "▲", cls: "text-up border-up/40" },
  partial: { label: "Partial", mark: "◐", cls: "text-down border-down/40" },
  missed: { label: "Missed", mark: "▼", cls: "text-down border-down/40" },
  pending: { label: "Pending", mark: "…", cls: "text-muted border-hairline" },
  not_verifiable: { label: "Not in tables", mark: "–", cls: "text-muted border-hairline" },
};

export function Chip({ v }: { v: LedgerVerdict }) {
  const x = VERDICT[v];
  return <span className={`whitespace-nowrap rounded border px-1.5 py-px text-[11px] ${x.cls}`}><span aria-hidden>{x.mark} </span>{x.label}</span>;
}

function MethodNote({ m }: { m?: Method }) {
  if (m !== "rules") return null;
  return <p className="mt-3 text-[11px] text-muted">Read by fixed rules from the documents, quoted verbatim. Written analysis switches on with a model key.</p>;
}

const fmtNum = (v: number) => v.toLocaleString("en-IN", { maximumFractionDigits: 2 });
export function targetText(t: Target | null | undefined): string {
  if (!t) return "—";
  if (t.direction && t.lo === null) return t.direction === "up" ? "↑ up" : t.direction === "down" ? "↓ down" : "flat";
  if (t.lo === null) return "—";
  const u = t.unit === "%" ? "%" : t.unit === "INR cr" ? " cr" : t.unit === "USD bn" ? " bn $" : ` ${t.unit}`;
  if (t.hi === null) return `${fmtNum(t.lo)}${u}+`;
  return t.lo === t.hi ? `${fmtNum(t.lo)}${u}` : `${fmtNum(t.lo)}–${fmtNum(t.hi)}${u}`;
}

export function VerdictCard({ card, ledger }: { card?: ResearchCard; ledger?: ResearchCard }) {
  const d = card?.data as VerdictData | null;
  const ask = useAsk();
  const sum = (ledger?.data as LedgerData | null)?.summary;
  return (
    <section id="verdict" className="scroll-mt-24 rounded-xl border border-ink/80 bg-raised px-4 py-4">
      <p className="text-[11px] uppercase tracking-wider text-muted">Verdict</p>
      {!card ? <p className="mt-1 font-serif text-[19px] text-muted">Reading the calls…</p>
        : <p className="mt-1 font-serif text-[20px] leading-snug">{d?.verdict ?? card.gaps.join(" ")}</p>}
      {sum && (
        <a href="#ledger" className="mt-3 flex flex-wrap gap-1.5" aria-label="Guidance tally; jump to the ledger">
          {(Object.keys(VERDICT) as LedgerVerdict[]).filter((v) => sum[v]).map((v) => (
            <span key={v} className={`num rounded border px-1.5 py-px text-[11px] ${VERDICT[v].cls}`}>{VERDICT[v].mark} {sum[v]} {VERDICT[v].label.toLowerCase()}</span>
          ))}
        </a>
      )}
      <button onClick={() => ask({ card: "verdict" })} className="mt-3 text-[13px] font-medium underline underline-offset-2">Ask FINN about {"this company"} →</button>
    </section>
  );
}

export function LedgerCard({ card }: { card?: ResearchCard }) {
  const d = card?.data as LedgerData | null;
  return (
    <CardShell id="ledger" title="Promised vs delivered" card={card}>
      {d && <>
        <p className="mt-1 text-[13px] text-muted">{d.pattern}</p>
        <p className="num mt-1 text-[11px] text-muted">Calls read: {d.calls.join(" · ")}</p>
        <ul className="mt-3 divide-y divide-hairline">
          {d.items.map((i) => <LedgerRow key={i.id} i={i} calls={d.calls} />)}
        </ul>
        <MethodNote m={d.method} />
      </>}
    </CardShell>
  );
}

function LedgerRow({ i, calls }: { i: LedgerItem; calls: string[] }) {
  const last = i.quarters[i.quarters.length - 1];
  const byCall = Object.fromEntries(i.quarters.map((q) => [q.period, q]));
  return (
    <li className="py-3">
      <div className="flex items-start justify-between gap-2">
        <p className="font-medium">{i.metric}</p>
        <Chip v={i.verdict} />
      </div>
      {/* threads × calls: what was guided on each call, revisions marked */}
      <div className="mt-2 grid gap-1" style={{ gridTemplateColumns: `repeat(${calls.length}, minmax(0, 1fr))` }}>
        {calls.map((c, k) => {
          const q = byCall[c];
          const prev = calls.slice(0, k).map((p) => byCall[p]).filter(Boolean).pop();
          const revised = q && prev && targetText(q.target) !== targetText(prev.target);
          return (
            <div key={c} className={`min-w-0 overflow-hidden rounded border px-1.5 py-1 ${q ? "border-hairline" : "border-dashed border-hairline/70"}`}>
              <p className="num whitespace-nowrap text-[10px] text-muted">{c.replace(/ 20(\d\d)$/, " '$1")}</p>
              {q ? <>
                <p className="num whitespace-nowrap text-[12px]">{targetText(q.target)}{revised && <span className="text-muted" title="Revised"> ↻</span>}</p>
                <div className="-ml-1 mt-0.5"><Cite ids={[q.said_citation]} /></div>
              </> : <p className="text-[12px] text-muted">—</p>}
            </div>
          );
        })}
      </div>
      <p className="mt-1.5 text-[13px]">{i.note}{i.actual_citations.length > 0 && <Cite ids={i.actual_citations} unit="₹ cr" note="Actual, from the reported tables" />}</p>
      {i.revisions.map((r) => <p key={r.to_period} className="num text-[11px] text-muted">↻ {r.from_period} → {r.to_period}: {r.change}</p>)}
      {last.said && <p className="mt-1 text-[12px] italic text-muted">“{last.said}”</p>}
    </li>
  );
}

const STATUS = { agrees: "✓ agrees", diverges: "✗ diverges", mixed: "~ mixed", untestable: "untestable" };

export function NarrativeCard({ card }: { card?: ResearchCard }) {
  const d = card?.data as NarrativeData | null;
  return (
    <CardShell id="narrative" title="Narrative vs numbers" card={card}>
      {d && <>
        <p className="mt-1 font-serif text-[16px]">{d.headline}</p>
        <ul className="mt-2 divide-y divide-hairline">
          {d.rows.map((r) => (
            <li key={r.claim_citation + r.topic} className="py-2.5">
              <div className="flex items-center justify-between gap-2 text-[11px] uppercase tracking-wide text-muted">
                <span>{r.topic.replace("_", " ")}</span>
                <span className={r.status === "diverges" ? "text-down" : r.status === "agrees" ? "text-up" : ""}>{STATUS[r.status]}</span>
              </div>
              <p className="mt-0.5 text-[13px]">Said: “{r.claim}”<Cite ids={[r.claim_citation]} /></p>
              <p className="text-[13px] text-muted">Numbers: {r.evidence}<Cite ids={r.evidence_citations} unit="₹ cr" /></p>
            </li>
          ))}
        </ul>
        <MethodNote m={d.method} />
      </>}
    </CardShell>
  );
}

export function SnapshotCard({ card }: { card?: ResearchCard }) {
  const d = card?.data as SnapshotData | null;
  return (
    <CardShell id="snapshot" title="Business snapshot" card={card}>
      {d && <>
        <p className="mt-1 font-serif text-[16px]">{d.what_it_does}</p>
        {d.segments.length > 0 && <ul className="mt-2 text-[13px]">
          {d.segments.map((s) => <li key={s.name}><span className="font-medium">{s.name}</span>
            {s.revenue_share_pct !== null && <span className="num"> · {s.revenue_share_pct}%</span>} — {s.description}<Cite ids={[s.citation]} /></li>)}
        </ul>}
        {d.key_facts.length > 0 && <ul className="mt-2 space-y-0.5 text-[13px]">
          {d.key_facts.map((f) => <li key={f.text}>— {f.text}<Cite ids={[f.citation]} /></li>)}
        </ul>}
      </>}
    </CardShell>
  );
}

export function GuidanceCard({ card }: { card?: ResearchCard }) {
  const d = card?.data as GuidanceData | null;
  return (
    <CardShell id="guidance" title="Latest guidance" card={card}>
      {d && <>
        <p className="mt-1 text-[12px] text-muted">From the {d.call} call</p>
        <ul className="mt-2 divide-y divide-hairline">
          {d.items.map((g) => (
            <li key={g.citation + g.metric} className="py-2">
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-medium">{g.metric_label} <span className="num text-[12px] text-muted">{g.horizon}</span></span>
                <span className="num">{targetText({ lo: g.target_lo, hi: g.target_hi, unit: g.unit, horizon: g.horizon, direction: g.direction as Target["direction"] })}</span>
              </div>
              <p className="text-[12px] italic text-muted">“{g.quote}”<Cite ids={[g.citation]} /></p>
            </li>
          ))}
        </ul>
        <MethodNote m={d.method} />
      </>}
    </CardShell>
  );
}

export function BullBearCard({ card }: { card?: ResearchCard }) {
  const d = card?.data as BullBearData | null;
  const side = (title: string, xs: BullBearData["bull"], mark: string) => (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-muted">{title}</p>
      {xs.length ? <ul className="mt-1 space-y-1.5 text-[13px]">
        {xs.map((p) => <li key={p.point}><span aria-hidden className="text-muted">{mark} </span>{p.point}<Cite ids={p.citations} unit="₹ cr" /></li>)}
      </ul> : <p className="mt-1 text-[13px] text-muted">Nothing in the sources argues this side clearly.</p>}
    </div>
  );
  return (
    <CardShell id="bull_bear" title="Bull vs bear" card={card}>
      {d && <>
        <div className="mt-2 grid gap-4 sm:grid-cols-2">{side("Bull", d.bull, "▲")}{side("Bear", d.bear, "▼")}</div>
        <p className="mt-3 border-t border-hairline pt-2 text-[13px]"><span className="text-muted">Swing factor: </span>{d.swing_factor}</p>
        <p className="mt-2 text-[11px] text-muted">No price targets or recommendations.</p>
        <MethodNote m={d.method} />
      </>}
    </CardShell>
  );
}
