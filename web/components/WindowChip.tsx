"use client";

export type WindowKey = "24h" | "3d" | "7d" | "custom";
export const WINDOW_HOURS: Record<Exclude<WindowKey, "custom">, number> = { "24h": 24, "3d": 72, "7d": 168 };

export function WindowChip({ value, onChange, custom, onCustom, max }: {
  value: WindowKey;
  onChange: (w: WindowKey) => void;
  custom: { from: string; to: string };
  onCustom: (c: { from: string; to: string }) => void;
  max: string; // yyyy-mm-dd, the last day with data
}) {
  const keys: WindowKey[] = ["24h", "3d", "7d", "custom"];
  return (
    <div>
      <div role="radiogroup" aria-label="Time window" className="inline-flex rounded-full border border-hairline p-0.5">
        {keys.map((k) => (
          <button key={k} role="radio" aria-checked={value === k} onClick={() => onChange(k)}
            className={`num rounded-full px-3 py-1 text-[12px] transition-colors ${
              value === k ? "bg-ink text-paper" : "text-muted hover:text-ink"}`}>
            {k === "custom" ? "Custom" : k}
          </button>
        ))}
      </div>
      {value === "custom" && (
        <div className="mt-2 flex items-center gap-2 text-[12px] text-muted">
          <label className="flex items-center gap-1">From
            <input type="date" value={custom.from} max={custom.to || max} onChange={(e) => onCustom({ ...custom, from: e.target.value })}
              className="num rounded border border-hairline bg-raised px-1.5 py-0.5 text-ink" />
          </label>
          <label className="flex items-center gap-1">to
            <input type="date" value={custom.to} min={custom.from} max={max} onChange={(e) => onCustom({ ...custom, to: e.target.value })}
              className="num rounded border border-hairline bg-raised px-1.5 py-0.5 text-ink" />
          </label>
        </div>
      )}
    </div>
  );
}
