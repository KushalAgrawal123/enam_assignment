"use client";

import { useState } from "react";
import { fmt, periodLabel } from "@/lib/format";

type Pt = { period: string; value: number };

/** Single-series bars: one neutral hue, 2px gaps, rounded data-end; tap a bar for its value. */
export function MiniBars({ points, unit, annual = true, height = 56 }: { points: Pt[]; unit: string; annual?: boolean; height?: number }) {
  const [hi, setHi] = useState<number | null>(null);
  if (points.length < 2) return null;
  const max = Math.max(...points.map((p) => Math.abs(p.value)), 1);
  const w = 100 / points.length;
  const shown = hi ?? points.length - 1;
  return (
    <figure>
      <svg viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" className="h-14 w-full" role="img"
        aria-label={`${points.length} periods, ${periodLabel(points[0].period, annual)} to ${periodLabel(points.at(-1)!.period, annual)}`}>
        {points.map((p, i) => {
          const h = Math.max(1, (Math.abs(p.value) / max) * (height - 2));
          return (
            <rect key={p.period} x={i * w + 0.6} width={w - 1.2} y={height - h} height={h} rx="1"
              fill={i === shown ? "var(--ink)" : "var(--muted)"} opacity={i === shown ? 1 : 0.45}
              onPointerEnter={() => setHi(i)} onClick={() => setHi(i)}>
              <title>{`${periodLabel(p.period, annual)}: ${fmt(p.value, unit)}`}</title>
            </rect>
          );
        })}
      </svg>
      <figcaption className="mt-1 flex justify-between text-[11px] text-muted">
        <span className="num">{periodLabel(points[0].period, annual)}</span>
        <span className="num text-ink">{periodLabel(points[shown].period, annual)}: {fmt(points[shown].value, unit)}</span>
        <span className="num">{periodLabel(points.at(-1)!.period, annual)}</span>
      </figcaption>
    </figure>
  );
}

/** Single-series line for percentages (margins): 2px stroke, end dot. */
export function MiniLine({ points, unit = "%" }: { points: Pt[]; unit?: string }) {
  if (points.length < 2) return null;
  const vs = points.map((p) => p.value);
  const lo = Math.min(...vs), hi = Math.max(...vs), span = hi - lo || 1;
  const xy = vs.map((v, i) => [(i / (vs.length - 1)) * 96 + 2, 22 - ((v - lo) / span) * 18]);
  return (
    <svg viewBox="0 0 100 26" className="h-7 w-full" role="img"
      aria-label={`from ${fmt(vs[0], unit)} to ${fmt(vs.at(-1)!, unit)}`}>
      <polyline points={xy.map(([x, y]) => `${x},${y}`).join(" ")} fill="none" stroke="var(--ink)" strokeWidth="1.5"
        vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
      <circle cx={xy.at(-1)![0]} cy={xy.at(-1)![1]} r="1.8" fill="var(--ink)" />
    </svg>
  );
}
