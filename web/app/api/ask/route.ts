import { forward } from "@/lib/server-api";

export async function POST(req: Request) {
  return forward("/ask", { method: "POST", body: await req.text() });
}
