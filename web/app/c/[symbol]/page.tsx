import { cacheLife } from "next/cache";
import { Suspense } from "react";
import { BottomNav } from "@/components/BottomNav";
import { ResearchSkeleton, ResearchView } from "@/components/research/ResearchView";
import type { ResearchPayload } from "@/lib/types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

// Research already built for this symbol is fetched on the server (cached a few minutes) and streamed with the page;
// the client then refreshes, reads documents and builds the analysis as before.
async function initialResearch(symbol: string): Promise<ResearchPayload | null> {
  "use cache";
  cacheLife("minutes");
  if (!API) return null;
  try {
    const r = await fetch(`${API}/research/${encodeURIComponent(symbol)}`, { signal: AbortSignal.timeout(8000) });
    if (!r.ok) return null;
    const p = await r.json();
    return p?.cards ? (p as ResearchPayload) : null;
  } catch {
    return null;
  }
}

async function Research({ params }: { params: Promise<{ symbol: string }> }) {
  const s = decodeURIComponent((await params).symbol).toUpperCase();
  return <ResearchView key={s} symbol={s} initial={await initialResearch(s)} />;
}

export default function ResearchPage({ params }: PageProps<"/c/[symbol]">) {
  return (
    <Suspense fallback={<ResearchSkeleton symbol="" />}>
      <Research params={params} />
      <BottomNav />
    </Suspense>
  );
}
