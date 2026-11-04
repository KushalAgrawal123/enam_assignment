"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ICON: Record<string, React.ReactNode> = {
  "/": <path d="M5 4h14v16H5zM8.5 8.5h7M8.5 12h7M8.5 15.5h4" />,
  "/watch": <path d="M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6zM12 14.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z" />,
  "/lookup": <path d="M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13zM15.5 15.5 20 20" />,
};
const ITEMS: { href: string; label: string }[] = [{ href: "/", label: "Brief" }, { href: "/watch", label: "Watch" }, { href: "/lookup", label: "Look up" }];

const active = (path: string, href: string) => href === "/" ? path === "/" : path.startsWith(href) || (href === "/lookup" && path.startsWith("/c/"));

export function BottomNav() {
  const path = usePathname();
  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-hairline bg-paper/95 pb-[env(safe-area-inset-bottom)] backdrop-blur">
      <ul className="mx-auto flex max-w-[560px]">
        {ITEMS.map((i) => {
          const on = active(path, i.href);
          return (
            <li key={i.href} className="flex-1">
              <Link href={i.href} aria-current={on ? "page" : undefined}
                className={`flex flex-col items-center gap-0.5 pb-2 pt-2.5 text-[11px] ${on ? "font-medium text-ink" : "text-muted"}`}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={on ? 1.9 : 1.5}
                  strokeLinecap="round" strokeLinejoin="round" aria-hidden>{ICON[i.href]}</svg>
                {i.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
