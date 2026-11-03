import type { MgmtCard as MC, Person } from "@/lib/types";

const VERB: Record<Person["action"], string> = { appointment: "joins", resignation: "resigns", cessation: "leaves",
  redesignation: "moves", retirement: "retires" };

function P({ p }: { p: Person }) {
  return (
    <li className="py-1.5">
      <p><span className="font-medium">{p.name}</span> <span className="text-muted">{VERB[p.action]}{p.role ? ` as ${p.role}` : ""}
        {p.effective_date ? `, from ${p.effective_date}` : ""}</span></p>
      {p.reason && <p className="text-[12px] text-muted">Reason given: {p.reason}</p>}
      {p.bio?.headline && <p className="mt-0.5 font-serif text-[15px] italic">{p.bio.headline}</p>}
      {p.bio?.bullets?.length ? (
        <ul className="mt-0.5 space-y-0.5 text-[12px]">
          {p.bio.bullets.map((b) => <li key={b.url + b.text}>— {b.text} <a href={b.url} target="_blank" rel="noreferrer" className="text-muted underline">source</a></li>)}
        </ul>
      ) : p.bio?.note ? <p className="text-[12px] text-muted">{p.bio.note}</p> : null}
    </li>
  );
}

/** Who's leaving, who's arriving, and who the newcomer is. */
export function MgmtCard({ c }: { c: MC }) {
  return (
    <div className="mt-2 text-[13px]">
      {c.incoming.length > 0 && <><p className="text-[11px] uppercase tracking-wide text-muted">In</p><ul>{c.incoming.map((p) => <P key={p.name} p={p} />)}</ul></>}
      {c.outgoing.length > 0 && <><p className="mt-1 text-[11px] uppercase tracking-wide text-muted">Out</p><ul>{c.outgoing.map((p) => <P key={p.name} p={p} />)}</ul></>}
      {c.flags.length > 0 && <p className="mt-1 text-[12px]">▼ {c.flags.join("; ")}</p>}
      {c.incoming.some((p) => !p.bio) && <p className="mt-1 text-[11px] text-muted">Background search isn&apos;t switched on yet for this deployment.</p>}
    </div>
  );
}
