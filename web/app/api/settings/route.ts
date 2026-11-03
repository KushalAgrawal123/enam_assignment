import { forward } from "@/lib/server-api";

export async function PUT(req: Request) {
  return forward("/settings", { method: "PUT", body: await req.text() });
}
