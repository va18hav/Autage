import { Link, Navigate, NavLink, Outlet, Route, Routes } from 'react-router-dom'
import { DashboardPage } from './features/dashboard/dashboard-page'
import { IncidentLivePage } from './features/incident/pages/incident-live-page'
import { RunbooksPage } from './features/runbooks/runbooks-page'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/runbooks', label: 'Runbooks' },
] as const

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/runbooks" element={<RunbooksPage />} />
        <Route path="/incidents/:incidentId/live" element={<IncidentLivePage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

function AppShell() {
  return (
    <div className="flex min-h-screen flex-col bg-neutral-50 text-neutral-950 antialiased">
      <header className="border-b border-neutral-200/70 bg-white">
        <div className="mx-auto flex w-full max-w-6xl items-center gap-6 px-6 py-3.5 lg:px-8">
          <Link to="/dashboard" className="text-sm font-semibold tracking-tight">
            Autage
          </Link>
          <nav className="flex items-center gap-1">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-neutral-100 text-neutral-900'
                      : 'text-neutral-500 hover:text-neutral-900 hover:bg-neutral-50'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-10 lg:px-8">
        <Outlet />
      </main>
    </div>
  )
}
