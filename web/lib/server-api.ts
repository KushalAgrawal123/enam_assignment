import "server-only";

// Server-side calls to the Pull API. The write token lives only in the server environment (FINN_API_TOKEN),
// never in the browser bundle.
const API = process.env.NEXT_PUBLIC_API_URL ?? "";

export async function forward(path: string, init: RequestInit = {}): Promise<Response> {
  const token = process.env.FINN_API_TOKEN;
  if (!API || !token) {
    return Response.json({ error: "not_configured", detail: "Saving rules isn't switched on for this deployment yet." }, { status: 503 });
  }
  const r = await fetch(API + path, { ...init, cache: "no-store",
    headers: { "Content-Type": "application/json", "X-FINN-Token": token, ...(init.headers ?? {}) } });
  return new Response(await r.text(), { status: r.status, headers: { "Content-Type": "application/json" } });
}
