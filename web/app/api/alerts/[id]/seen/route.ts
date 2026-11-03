import { forward } from "@/lib/server-api";

export async function POST(_req: Request, ctx: RouteContext<"/api/alerts/[id]/seen">) {
  const { id } = await ctx.params;
  if (!/^\d+$/.test(id)) return Response.json({ error: "bad_id", detail: "Alert id must be a number." }, { status: 400 });
  return forward(`/alerts/${id}/seen`, { method: "POST" });
}
