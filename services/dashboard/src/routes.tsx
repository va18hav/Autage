import { useState } from 'react'
import { Link, Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { PanelLeft } from 'lucide-react'

import { AuthPage } from './features/auth/auth-page'
import { useAuthStatus } from './features/auth/hooks/use-auth'
import { DashboardPage } from './features/dashboard/dashboard-page'
import { IncidentLivePage } from './features/incident/pages/incident-live-page'
import { IncidentsPage } from './features/incident/pages/incidents-page'
import { OnboardingPage } from './features/onboarding/onboarding-page'
import { RunbooksPage } from './features/runbooks/runbooks-page'
import { IntegrationsPage } from './features/settings/integrations-page'
import { SettingsPage } from './features/settings/settings-page'
import { BrandLogo } from './shared/components/brand-logo'
import { Sidebar } from './shared/components/sidebar'
import type { AuthUser } from './shared/types/auth'

export function AppRoutes() {
  const { data: auth, isPending } = useAuthStatus()

  if (isPending) {
    return (
      <div className="flex h-screen items-center justify-center bg-white">
        <div className="size-4 animate-spin rounded-full border-2 border-neutral-200 border-t-neutral-900" />
      </div>
    )
  }

  if (!auth?.initialized) {
    return <AuthPage mode="setup" />
  }

  if (!auth.authenticated || !auth.user) {
    return <AuthPage mode="login" />
  }

  return (
    <Routes>
      <Route path="/onboarding" element={<OnboardingPage />} />
      <Route element={<AppShell user={auth.user} />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/incidents" element={<IncidentsPage />} />
        <Route path="/runbooks" element={<RunbooksPage />} />
        <Route path="/integrations" element={<IntegrationsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/incidents/:incidentId/live" element={<IncidentLivePage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

function AppShell({ user }: { user: AuthUser }) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden bg-white text-foreground antialiased selection:bg-neutral-900 selection:text-white">
      <Sidebar
        user={user}
        collapsed={collapsed}
        onCollapsedChange={setCollapsed}
        mobileOpen={mobileOpen}
        onMobileOpenChange={setMobileOpen}
      />

      <div className="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-white">
        {/* Desktop Expand Sidebar Trigger */}
        {collapsed && (
          <div className="absolute top-4 left-4 z-30 hidden md:block">
            <button
              type="button"
              onClick={() => setCollapsed(false)}
              title="Expand sidebar"
              aria-label="Expand sidebar"
              className="flex size-8 cursor-pointer items-center justify-center rounded-lg text-neutral-500 transition-colors duration-100 hover:bg-neutral-100 hover:text-neutral-900"
            >
              <PanelLeft className="size-[18px]" strokeWidth={1.75} />
            </button>
          </div>
        )}

        {/* Mobile Sidebar Toggle Bar */}
        <header className="flex h-13 shrink-0 items-center justify-between border-b border-neutral-100 bg-white px-4 md:hidden">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            aria-label="Open sidebar"
            className="flex size-9 cursor-pointer items-center justify-center rounded-lg text-neutral-600 transition-colors hover:bg-neutral-100 hover:text-neutral-900"
          >
            <PanelLeft className="size-5" strokeWidth={1.75} />
          </button>

          <Link
            to="/dashboard"
            className="focus-visible:outline-none"
          >
            <BrandLogo iconClassName="size-6" textClassName="text-[16px]" />
          </Link>

          <div className="size-9" aria-hidden="true" />
        </header>

        <main className="flex-1 overflow-y-auto bg-white [scrollbar-gutter:stable]">
          <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-8 sm:py-10 lg:px-12">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
