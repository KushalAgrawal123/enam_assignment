import type { PricePoint } from "@/lib/types";

/** Last `n` closes as a hairline; the end dot marks the latest close. Decorative: the number beside it carries
 *  the information, so it's hidden from screen readers. */
export function Sparkline({ points, n = 30, width = 72, height = 22 }: {
  points: PricePoint[] | undefined; n?: number; width?: number; height?: number;
}) {
  const p = (points ?? []).slice(-n);
  if (p.length < 2) return <span className="inline-block" style={{ width, height }} aria-hidden />;
  const closes = p.map((x) => x.close);
  const lo = Math.min(...closes);
  const hi = Math.max(...closes);
  const span = hi - lo || 1;
  const xy = closes.map((c, i) => [
    (i / (closes.length - 1)) * (width - 3) + 1.5,
    height - 1.5 - ((c - lo) / span) * (height - 3),
  ]);
  const up = closes.at(-1)! >= closes[0];
  const [ex, ey] = xy.at(-1)!;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden className="shrink-0">
      <polyline points={xy.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ")} fill="none"
        stroke="var(--muted)" strokeWidth="1" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={ex} cy={ey} r="1.8" fill={up ? "var(--up)" : "var(--down)"} />
    </svg>
  );
}

/** Close-to-close move of the latest session. */
export function dayMove(points: PricePoint[] | undefined): number | null {
  const p = points ?? [];
  if (p.length < 2 || !p.at(-2)!.close) return null;
  return (p.at(-1)!.close / p.at(-2)!.close - 1) * 100;
}
