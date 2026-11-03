"use client";

import { useRef, useState, type ReactNode } from "react";

/** Horizontal swipe: left = Noted, right = Snooze. Vertical scrolling is left alone. */
export function Swipeable({ onNoted, onSnooze, children }: { onNoted: () => void; onSnooze: () => void; children: ReactNode }) {
  const start = useRef<{ x: number; y: number } | null>(null);
  const [dx, setDx] = useState(0);
  const [locked, setLocked] = useState<"h" | "v" | null>(null);
  const [dragging, setDragging] = useState(false);
  const LIMIT = 96;
  return (
    <div className="relative overflow-hidden rounded-xl">
      <div aria-hidden className="absolute inset-0 flex items-center justify-between px-5 text-[12px] font-medium">
        <span className={`text-muted transition-opacity ${dx > 24 ? "opacity-100" : "opacity-0"}`}>Snooze till 8am</span>
        <span className={`text-muted transition-opacity ${dx < -24 ? "opacity-100" : "opacity-0"}`}>Noted ✓</span>
      </div>
      <div
        style={{ transform: `translateX(${dx}px)`, transition: dragging ? "none" : "transform 150ms ease", touchAction: "pan-y" }}
        onPointerDown={(e) => { if (e.pointerType !== "mouse") { start.current = { x: e.clientX, y: e.clientY }; setLocked(null); setDragging(true); } }}
        onPointerMove={(e) => {
          if (!start.current) return;
          const x = e.clientX - start.current.x, y = e.clientY - start.current.y;
          const lock = locked ?? (Math.abs(x) > 8 || Math.abs(y) > 8 ? (Math.abs(x) > Math.abs(y) ? "h" : "v") : null);
          if (lock !== locked) setLocked(lock);
          if (lock === "h") setDx(x);
        }}
        onPointerUp={() => {
          const d = dx;
          start.current = null;
          setDragging(false);
          setDx(0);
          if (d <= -LIMIT) onNoted();
          else if (d >= LIMIT) onSnooze();
        }}
        onPointerCancel={() => { start.current = null; setDragging(false); setDx(0); }}
        onClickCapture={(e) => { if (Math.abs(dx) > 8) e.stopPropagation(); }}
      >
        {children}
      </div>
    </div>
  );
}

export function TriageButtons({ onNoted, onSnooze }: { onNoted: () => void; onSnooze: () => void }) {
  return (
    <div className="mt-3 flex gap-2 text-[12px]">
      <button onClick={onNoted} className="rounded-full border border-hairline px-3 py-1 hover:border-muted">Noted</button>
      <button onClick={onSnooze} className="rounded-full border border-hairline px-3 py-1 text-muted hover:border-muted">Snooze till 8am</button>
    </div>
  );
}
