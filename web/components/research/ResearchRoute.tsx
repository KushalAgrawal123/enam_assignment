"use client";

import { useParams } from "next/navigation";
import { ResearchView } from "./ResearchView";

export function ResearchRoute() {
  const { symbol } = useParams<{ symbol: string }>();
  const s = decodeURIComponent(symbol).toUpperCase();
  return <ResearchView key={s} symbol={s} />;
}
