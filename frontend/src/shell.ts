import { useOutletContext } from "react-router-dom";
import type { DashboardStats, Listing, SetupStatus } from "./api";
import type { useScan } from "./hooks/useScan";

export interface ShellContext {
  listings: Listing[];
  stats: DashboardStats | null;
  setup: SetupStatus | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
  scan: ReturnType<typeof useScan>;
}

/**
 * The shell fetches listings once and shares them, so the nav deal badge and
 * the Deals headline can never disagree about how many deals there are.
 */
export function useShell() {
  return useOutletContext<ShellContext>();
}
