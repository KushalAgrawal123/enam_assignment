import { stamp, when } from "@/lib/format";

/** The end of the brief. Getting here is the point. */
export function CaughtUp({ windowLabel, asOf, mode }: { windowLabel: string; asOf: string; mode: "live" | "demo" }) {
  return (
    <footer className="mt-10 text-center">
      <p className="font-serif text-[22px] italic">You&apos;re caught up.</p>
      <p className="mt-1 text-[12px] text-muted">
        That&apos;s everything that mattered {windowLabel}.{" "}
        {mode === "live" ? <>Checked <span className="num">{when(asOf, asOf)}</span> IST; new filings are checked every 15 minutes.</>
          : <>Demo snapshot frozen <span className="num">{stamp(asOf)}</span> IST.</>}
      </p>
    </footer>
  );
}
