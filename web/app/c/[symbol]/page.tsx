import { Suspense } from "react";
import { BottomNav } from "@/components/BottomNav";
import { ResearchRoute } from "@/components/research/ResearchRoute";

// The symbol and path are request data, so both client parts sit behind Suspense (Cache Components rule).
export default function ResearchPage() {
  return (<Suspense fallback={null}><ResearchRoute /><BottomNav /></Suspense>);
}
