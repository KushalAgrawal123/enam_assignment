import { MgmtCard } from "@/components/cards/MgmtCard";
import { ResultsCard } from "@/components/cards/ResultsCard";
import type { DigestCard, PushCard } from "@/lib/types";

/** The answer under a filing's headline: numbers, people, or one line. Nothing when no card was built. */
export function CardBody({ c }: { c: DigestCard }) {
  const card = c.card as PushCard | null;
  if (!card) return null;
  if (card.type === "results") return <ResultsCard c={card} />;
  if (card.type === "management_change") return <MgmtCard c={card} />;
  if (card.type === "oneliner") return <p className="mt-2 text-[14px]">{card.line}</p>;
  return null;
}
