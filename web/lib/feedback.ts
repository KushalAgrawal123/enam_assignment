// Feedback loop: after repeated "Noted" swipes on one kind of filing, offer to treat that kind as routine.
// The choice applies on this device at once, and to the server's scoring (settings.weights) when it can save.
import { getSettings, putSettings } from "./api";
import { notedByCategory } from "./triage";
import type { Filing } from "./types";

const KEY = "finn.feedback";
export const THRESHOLD = 3;
// Never offered: these carry price-moving news even when you usually skip them.
const NEVER = new Set(["results", "M&A", "litigation", "pledging", "credit_rating", "management_change", "fund_raise"]);
export const ROUTINE_WEIGHT = 0.05;

type State = { routine: string[]; declined: string[] };
function read(): State {
  try { return { routine: [], declined: [], ...JSON.parse(localStorage.getItem(KEY) ?? "{}") }; } catch { return { routine: [], declined: [] }; }
}
function write(s: State) {
  try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* private mode */ }
}

export const routineCategories = () => new Set(read().routine);

/** The category to ask about now, if any. */
export function pendingOffer(): { category: string; count: number } | null {
  const s = read();
  const counts = notedByCategory();
  const hit = Object.entries(counts).filter(([c, n]) => n >= THRESHOLD && !NEVER.has(c) && !s.routine.includes(c) && !s.declined.includes(c))
    .sort((a, b) => b[1] - a[1])[0];
  return hit ? { category: hit[0], count: hit[1] } : null;
}

export function decline(category: string) {
  const s = read();
  write({ ...s, declined: [...s.declined, category] });
}

/** Accept: routine on this device now; returns whether the server's scoring was updated too. */
export async function acceptRoutine(category: string): Promise<boolean> {
  const s = read();
  write({ ...s, routine: [...new Set([...s.routine, category])] });
  try {
    const cur = await getSettings();
    await putSettings({ weights: { ...(cur.weights ?? {}), [category]: ROUTINE_WEIGHT } });
    return true;
  } catch {
    return false;
  }
}

export function undoRoutine(category: string) {
  const s = read();
  write({ ...s, routine: s.routine.filter((c) => c !== category) });
}

/** Apply this device's routine choices to filings before the digest is built. */
export function applyRoutine(filings: Filing[], routine: Set<string>): Filing[] {
  if (!routine.size) return filings;
  return filings.map((f) => (routine.has(f.category) && f.tier !== "routine" ? { ...f, tier: "routine" } : f));
}
