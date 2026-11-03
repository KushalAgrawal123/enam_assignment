"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// Only screens that exist are listed (PLAN Phase 1). Watch and Look up join in later phases.
const ITEMS: { href: string; label: string }[] = [{ href: "/", label: "Brief" }];

export function BottomNav() {
  const path = usePathname();
  if (ITEMS.length < 2) return null; // a one-item nav is noise
  return (
    <nav className="fixed inset-x-0 bottom-0 border-t border-hairline bg-paper/95 pb-[env(safe-area-inset-bottom)] backdrop-blur">
      <ul className="mx-auto flex max-w-[560px]">
        {ITEMS.map((i) => (
          <li key={i.href} className="flex-1">
            <Link href={i.href} aria-current={path === i.href ? "page" : undefined}
              className={`block py-3 text-center text-[12px] ${path === i.href ? "text-ink" : "text-muted"}`}>
              {i.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
