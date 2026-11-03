import { cacheLife } from "next/cache";
import { BottomNav } from "@/components/BottomNav";
import { Brief } from "@/components/brief/Brief";
import { loadLive } from "@/lib/data";

// The live brief is fetched on the server and cached for a few minutes, so the first paint already has it.
async function initialBrief() {
  "use cache";
  cacheLife("minutes");
  try {
    return await loadLive();
  } catch {
    return null;   // stale or unreachable: the client falls back to the demo snapshot, as before
  }
}

export default async function Page() {
  const initial = await initialBrief();
  return (
    <>
      <Brief initial={initial} />
      <BottomNav />
    </>
  );
}
