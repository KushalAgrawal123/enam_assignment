import { cacheLife } from "next/cache";
import { BottomNav } from "@/components/BottomNav";
import { Watch } from "@/components/Watch";
import { loadLive } from "@/lib/data";

async function initialData() {
  "use cache";
  cacheLife("minutes");
  try {
    return await loadLive();
  } catch {
    return null;
  }
}

export default async function WatchPage() {
  return (<><Watch initial={await initialData()} /><BottomNav /></>);
}
