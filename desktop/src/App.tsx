import { NavLink, Route, Routes } from "react-router-dom";
import CatalogPage from "./pages/CatalogPage";
import CredentialsPage from "./pages/CredentialsPage";
import FlowsPage from "./pages/FlowsPage";
import HomePage from "./pages/HomePage";
import RunsPage from "./pages/RunsPage";
import SchedulesPage from "./pages/SchedulesPage";
import SyncPage from "./pages/SyncPage";

const links = [
  { to: "/", label: "Home", end: true },
  { to: "/credentials", label: "Credentials" },
  { to: "/connectors", label: "Connectors" },
  { to: "/flows", label: "Flows" },
  { to: "/runs", label: "Runs" },
  { to: "/schedules", label: "Schedules" },
  { to: "/sync", label: "Sync" },
];

/** Root shell with sidebar navigation. */
export default function App() {
  return (
    <div className="min-h-screen grid grid-cols-[220px_1fr]">
      <aside className="border-r border-slate-800 bg-slate-950 p-4 flex flex-col gap-4">
        <div>
          <div className="text-lg font-semibold tracking-wide">Navbe</div>
          <div className="text-xs muted">Local ops console</div>
        </div>
        <nav className="flex flex-col gap-1">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) =>
                `nav-link rounded-lg px-3 py-2 text-sm ${isActive ? "active" : "hover:bg-slate-900"}`
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="p-6 overflow-auto">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/credentials" element={<CredentialsPage />} />
          <Route path="/connectors" element={<CatalogPage />} />
          <Route path="/flows" element={<FlowsPage />} />
          <Route path="/runs" element={<RunsPage />} />
          <Route path="/schedules" element={<SchedulesPage />} />
          <Route path="/sync" element={<SyncPage />} />
        </Routes>
      </main>
    </div>
  );
}
