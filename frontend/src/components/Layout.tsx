import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { api } from "../api";

const navItems = [
  { to: "/", label: "Dashboard" },
  { to: "/watchlist", label: "Watchlist" },
  { to: "/listings", label: "Listings" },
  { to: "/history", label: "History" },
];

export default function Layout() {
  const [fbStatus, setFbStatus] = useState<boolean | null>(null);

  useEffect(() => {
    api.getFbStatus().then((s) => setFbStatus(s.logged_in)).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-gray-900">
              Marketplace Sniper
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex gap-1">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    `px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-blue-100 text-blue-700"
                        : "text-gray-600 hover:bg-gray-100"
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
            <div
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full ${
                fbStatus === true
                  ? "bg-green-50 text-green-700"
                  : fbStatus === false
                    ? "bg-red-50 text-red-600"
                    : "bg-gray-50 text-gray-400"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  fbStatus === true
                    ? "bg-green-500"
                    : fbStatus === false
                      ? "bg-red-400"
                      : "bg-gray-300"
                }`}
              />
              FB {fbStatus === true ? "Connected" : fbStatus === false ? "Not Connected" : "..."}
            </div>
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
