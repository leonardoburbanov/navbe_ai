import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { invoke } from "@tauri-apps/api/core";
import CatalogPage from "./pages/CatalogPage";
import CredentialsPage from "./pages/CredentialsPage";
import FlowsPage from "./pages/FlowsPage";
import HomePage from "./pages/HomePage";
import RunsPage from "./pages/RunsPage";
import SchedulesPage from "./pages/SchedulesPage";
import SyncPage from "./pages/SyncPage";
import type { DaemonStatus } from "./api/types";

const primaryLinks = [
  { to: "/", label: "Home", end: true, hint: "Start here" },
  { to: "/flows", label: "Flows", hint: "Build & run" },
  { to: "/runs", label: "Results", hint: "What happened" },
];

const secondaryLinks = [
  { to: "/credentials", label: "Credentials" },
  { to: "/catalog", label: "Catalog" },
  { to: "/schedules", label: "Schedules" },
  { to: "/sync", label: "Sync" },
];

/** Root shell with simple primary / more navigation. */
export default function App() {
  const daemon = useQuery({
    queryKey: ["daemon-status-shell"],
    queryFn: async () => {
      try {
        return await invoke<DaemonStatus>("daemon_status");
      } catch {
        return null;
      }
    },
    refetchInterval: 5000,
  });
  const ready = Boolean(daemon.data?.running);

  return (
    <div className="app-shell">
      <aside className="app-rail">
        <div className="app-brand">
          <div className="app-brand__name">Navbe</div>
          <div className="app-brand__tag">Local workflows</div>
          <div className="engine-pill" title={daemon.data?.mcp_url ?? undefined}>
            <span className={`engine-pill__dot ${ready ? "engine-pill__dot--ok" : ""}`} />
            {ready ? "Online" : "Starting…"}
          </div>
        </div>
        <nav className="app-nav">
          {primaryLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
            >
              <span className="nav-link__label">{link.label}</span>
              <span className="nav-link__hint">{link.hint}</span>
            </NavLink>
          ))}
        </nav>
        <div className="app-nav-section">
          <div className="app-nav-section__label">More</div>
          <nav className="app-nav">
            {secondaryLinks.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) => `nav-link nav-link--quiet ${isActive ? "active" : ""}`}
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </aside>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/credentials" element={<CredentialsPage />} />
          <Route path="/catalog" element={<CatalogPage />} />
          <Route path="/connectors" element={<Navigate to="/catalog" replace />} />
          <Route path="/flows" element={<FlowsPage />} />
          <Route path="/runs" element={<RunsPage />} />
          <Route path="/schedules" element={<SchedulesPage />} />
          <Route path="/sync" element={<SyncPage />} />
        </Routes>
      </main>
    </div>
  );
}
