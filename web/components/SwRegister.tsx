"use client";

import { useEffect } from "react";

/** Registers public/sw.js: offline app shell + demo snapshot. Production only, so dev reloads stay honest. */
export function SwRegister() {
  useEffect(() => {
    if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);
  return null;
}
