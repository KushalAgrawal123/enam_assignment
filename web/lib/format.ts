// Display helpers. Times are stored in UTC and always shown in IST.
const IST = "Asia/Kolkata";

const timeFmt = new Intl.DateTimeFormat("en-IN", { timeZone: IST, hour: "2-digit", minute: "2-digit", hour12: false });
const dayFmt = new Intl.DateTimeFormat("en-IN", { timeZone: IST, weekday: "short", day: "numeric", month: "short" });
const longDayFmt = new Intl.DateTimeFormat("en-IN", { timeZone: IST, weekday: "long", day: "numeric", month: "long" });
const istDate = new Intl.DateTimeFormat("en-CA", { timeZone: IST, year: "numeric", month: "2-digit", day: "2-digit" });

export const istDay = (iso: string) => istDate.format(new Date(iso));
export const longDay = (iso: string) => longDayFmt.format(new Date(iso));

/** "14:05" today, "Mon 2 Nov · 14:05" otherwise, relative to `now`. */
export function when(iso: string, now: string): string {
  const d = new Date(iso);
  return istDay(iso) === istDay(now) ? timeFmt.format(d) : `${dayFmt.format(d)} · ${timeFmt.format(d)}`;
}

/** "3h ago" / "2d ago" relative to `now`. */
export function ago(iso: string, now: string): string {
  const mins = Math.max(0, Math.round((new Date(now).getTime() - new Date(iso).getTime()) / 60000));
  if (mins < 60) return `${mins}m ago`;
  if (mins < 48 * 60) return `${Math.round(mins / 60)}h ago`;
  return `${Math.round(mins / 1440)}d ago`;
}

/** Signed percentage with a direction glyph, so colour is never the only signal. */
export function pct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const glyph = v > 0 ? "▲" : v < 0 ? "▼" : "•";
  return `${glyph} ${v > 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

export function crore(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v >= 100000 ? `₹${(v / 100000).toFixed(2)} lakh cr` : `₹${Math.round(v).toLocaleString("en-IN")} cr`;
}

export const CATEGORY_LABEL: Record<string, string> = {
  results: "Results", "M&A": "Deal", fund_raise: "Fund raise", management_change: "Management",
  litigation: "Legal", insider_trading: "Insider trade", earnings_call: "Earnings call",
  investor_meetings: "Investor meet", credit_rating: "Rating", dividend: "Dividend", bonus_split: "Bonus/split",
  capex: "Capex", press_release: "News", postal_ballot: "Postal ballot", agm_egm: "Shareholder meeting",
  pledging: "Pledge", unclassified: "Routine",
};

export function shortName(name: string | undefined, symbol: string): string {
  if (!name) return "";
  const s = name.replace(/\b(Limited|Ltd\.?|Industries|Company|Technologies)\b|\(India\)/g, "").replace(/\s+/g, " ").trim();
  return s.toUpperCase() === symbol.toUpperCase() ? "" : s;
}

const shortFmt = new Intl.DateTimeFormat("en-IN", { timeZone: IST, day: "numeric", month: "short" });
/** "3 Nov 16:06" (IST). */
export const short = (iso: string) => `${shortFmt.format(new Date(iso))} ${timeFmt.format(new Date(iso))}`;

/** Always the full "Tue 3 Nov · 16:06" form (IST). */
export const stamp = (iso: string) => `${dayFmt.format(new Date(iso))} · ${timeFmt.format(new Date(iso))}`;

const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
/** Table period keys: "2026-03-31" -> "FY26" for annual tables, "Sep 2026" for quarters; TTM/current pass through. */
export function periodLabel(p: string, annual = false): string {
  const m = /^(\d{4})-(\d{2})-\d{2}$/.exec(p);
  if (!m) return p === "current" ? "now" : p;
  return annual && m[2] === "03" ? `FY${m[1].slice(2)}` : `${MON[Number(m[2]) - 1]} ${m[1]}`;
}

/** A value in its unit: "₹38,632 cr", "19%", "0.21x", "46 days". */
export function fmt(v: number | null | undefined, unit: string): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (unit === "₹ cr") return `₹${Math.round(v).toLocaleString("en-IN")} cr`;
  if (unit === "%") return `${Number.isInteger(v) ? v : v.toFixed(1)}%`;
  if (unit === "x") return `${v.toFixed(2)}×`;
  if (unit === "days") return `${Math.round(v)} days`;
  return Math.abs(v) >= 100 ? Math.round(v).toLocaleString("en-IN") : String(v);
}
