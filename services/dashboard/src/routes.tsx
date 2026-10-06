import { Navigate, NavLink, Outlet, Route, Routes } from 'react-router-dom'
import { LayoutDashboard, ScrollText } from 'lucide-react'
import { DashboardPage } from './features/dashboard/dashboard-page'
import { IncidentLivePage } from './features/incident/pages/incident-live-page'
import { RunbooksPage } from './features/runbooks/runbooks-page'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/runbooks', label: 'Runbooks', icon: ScrollText },
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
    <div className="flex min-h-screen flex-col bg-neutral-50/80 text-foreground antialiased">
      {/* Floating glass navbar island */}
      <nav className="fixed inset-x-0 top-4 z-50 flex justify-center px-4">
        <div className="flex items-center gap-1 rounded-full border border-neutral-200/60 bg-white/85 py-1.5 pr-1.5 pl-5 shadow-lg shadow-neutral-950/[0.06] backdrop-blur-xl">
          <span className="mr-3 flex items-center gap-2 text-sm font-semibold tracking-tight text-neutral-900">
            <span className="flex size-6 items-center justify-center rounded-full bg-neutral-900 text-[11px] font-bold text-white">
              A
            </span>
            Autage
          </span>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? 'bg-neutral-900 text-white shadow-sm'
                    : 'text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900'
                }`
              }
            >
              <item.icon className="size-4" />
              {item.label}
            </NavLink>
          ))}
        </div>
      </nav>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 pt-24 pb-10 lg:px-8">
        <Outlet />
      </main>
    </div>
  )
}
