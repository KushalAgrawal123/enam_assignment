// Triage state lives on this device (localStorage): Noted hides an item for good, Snooze until 08:00 IST tomorrow.
const KEY = "finn.triage";
type State = Record<string, { action: "noted" | "snoozed"; until?: string; at: string }>;

function read(): State {
  try { return JSON.parse(localStorage.getItem(KEY) ?? "{}"); } catch { return {}; }
}
function write(s: State) {
  try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* private mode: triage lasts this visit */ }
}

export function hiddenIds(now = new Date()): Set<string> {
  const s = read();
  return new Set(Object.entries(s).filter(([, v]) => v.action === "noted" || (v.until && new Date(v.until) > now)).map(([k]) => k));
}

export function tomorrow8IST(now = new Date()): string {
  const ist = new Date(now.getTime() + 330 * 60000);
  const d = new Date(Date.UTC(ist.getUTCFullYear(), ist.getUTCMonth(), ist.getUTCDate() + 1, 8, 0) - 330 * 60000);
  return d.toISOString();
}

export function triage(id: string, action: "noted" | "snoozed") {
  const s = read();
  s[id] = { action, at: new Date().toISOString(), until: action === "snoozed" ? tomorrow8IST() : undefined };
  write(s);
}

export function undo(id: string) {
  const s = read();
  delete s[id];
  write(s);
}

/** How often each category was marked Noted (feeds the "show as routine?" prompt in Phase 5). */
export function notedCount(): number {
  return Object.values(read()).filter((v) => v.action === "noted").length;
}
