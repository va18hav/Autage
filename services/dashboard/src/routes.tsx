import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { DashboardPage } from './features/dashboard/dashboard-page'
import { IncidentLivePage } from './features/incident/pages/incident-live-page'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/incidents/:incidentId/live" element={<IncidentLivePage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

function AppShell() {
  return (
    <div className="flex min-h-screen flex-col bg-neutral-50 text-neutral-950 antialiased">
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-10 lg:px-8">
        <Outlet />
      </main>
    </div>
  )
}
