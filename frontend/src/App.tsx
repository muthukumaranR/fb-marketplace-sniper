import { Link, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import Listings from "./pages/Listings";
import Watchlist from "./pages/Watchlist";

function NotFound() {
  return (
    <div className="text-center py-20">
      <p className="text-6xl font-bold text-gray-200">404</p>
      <p className="text-lg text-gray-500 mt-4">Page not found</p>
      <Link
        to="/"
        className="inline-block mt-6 px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700"
      >
        Back to Dashboard
      </Link>
    </div>
  );
}

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/watchlist" element={<Watchlist />} />
        <Route path="/listings" element={<Listings />} />
        <Route path="/history" element={<History />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}

export default App;
