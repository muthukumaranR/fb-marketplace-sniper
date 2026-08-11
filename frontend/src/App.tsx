import { Link, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { useListingFlags } from "./hooks/useListingFlags";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import Listings from "./pages/Listings";
import Watchlist from "./pages/Watchlist";

/**
 * Listings owns its own full-bleed layout (sticky filter rail), so the shell
 * adds no padding. Screens still on the pre-redesign layout keep the old
 * centered container until their redesign steps land.
 */
function Page({ children }: { children: React.ReactNode }) {
  return <div className="mx-auto max-w-7xl px-6 py-6">{children}</div>;
}

function NotFound() {
  return (
    <div className="py-20 text-center">
      <p className="font-mono text-6xl font-bold text-fg3">404</p>
      <p className="mt-4 text-[15px] text-fg2">Page not found</p>
      <Link
        to="/"
        className="mt-6 inline-block rounded-lg bg-fg px-4 py-2 text-[12.5px] font-bold text-bg"
      >
        Back to Deals
      </Link>
    </div>
  );
}

function App() {
  // Saved / dismissed are app-level so they survive navigation between screens.
  const { flags: saved, toggle: toggleSave } = useListingFlags("marketswipe-saved");
  const { flags: dismissed, toggle: toggleDismiss } =
    useListingFlags("marketswipe-dismissed");

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/watchlist" element={<Watchlist />} />
        <Route
          path="/listings"
          element={
            <Listings
              saved={saved}
              dismissed={dismissed}
              onToggleSave={toggleSave}
              onToggleDismiss={toggleDismiss}
            />
          }
        />
        <Route path="/history" element={<History />} />
        <Route
          path="*"
          element={
            <Page>
              <NotFound />
            </Page>
          }
        />
      </Route>
    </Routes>
  );
}

export default App;
