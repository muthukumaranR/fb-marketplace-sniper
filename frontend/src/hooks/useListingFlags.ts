import { useCallback, useEffect, useState } from "react";

export type FlagMap = Record<number, boolean>;

function load(key: string): FlagMap {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as FlagMap) : {};
  } catch {
    return {};
  }
}

/**
 * Saved / dismissed are local user state — the backend has no concept of them.
 * Dismissed listings are hidden from Results but never deleted, so the map only
 * ever stores a boolean per listing id.
 */
export function useListingFlags(key: string) {
  const [flags, setFlags] = useState<FlagMap>(() => load(key));

  useEffect(() => {
    localStorage.setItem(key, JSON.stringify(flags));
  }, [key, flags]);

  const toggle = useCallback((id: number) => {
    setFlags((f) => {
      const next = { ...f };
      if (next[id]) delete next[id];
      else next[id] = true;
      return next;
    });
  }, []);

  return { flags, toggle };
}
