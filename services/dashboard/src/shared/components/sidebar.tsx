import { useEffect } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { LogOut, PanelLeft, X } from 'lucide-react'

import { useIncidentList } from '../../features/dashboard/hooks/use-incidents'
import { authApi } from '../lib/api'
import { MAIN_NAV_ITEMS } from '../lib/navigation'
import { queryKeys } from '../lib/query-client'
import type { AuthUser } from '../types/auth'
import { BrandLogo } from './brand-logo'

interface SidebarProps {
  user: AuthUser
  collapsed: boolean
  onCollapsedChange: (collapsed: boolean) => void
  mobileOpen: boolean
  onMobileOpenChange: (open: boolean) => void
}

export function Sidebar({
  user,
  collapsed,
  onCollapsedChange,
  mobileOpen,
  onMobileOpenChange,
}: SidebarProps) {
  const location = useLocation()

  // Close mobile sidebar drawer automatically on route navigation
  useEffect(() => {
    onMobileOpenChange(false)
  }, [location.pathname, onMobileOpenChange])

  return (
    <>
      {/* Desktop Collapsible Sidebar */}
      <aside
        className={`hidden shrink-0 flex-col justify-between border-r border-neutral-200/60 bg-[#F9F9F9] transition-[width] duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] select-none md:flex ${
          collapsed ? 'w-0 overflow-hidden border-r-0' : 'w-[260px]'
        }`}
      >
        <SidebarBody
          user={user}
          onClose={() => onCollapsedChange(true)}
          isMobile={false}
        />
      </aside>

      {/* Mobile Slide-Over Sidebar Drawer */}
      <div
        className={`fixed inset-0 z-50 md:hidden ${
          mobileOpen ? 'pointer-events-auto' : 'pointer-events-none'
        }`}
      >
        {/* Backdrop */}
        <div
          onClick={() => onMobileOpenChange(false)}
          className={`fixed inset-0 bg-black/25 backdrop-blur-[1px] transition-opacity duration-200 ${
            mobileOpen ? 'opacity-100' : 'opacity-0'
          }`}
        />

        {/* Drawer Panel */}
        <aside
          className={`relative z-10 flex h-full w-[272px] max-w-[82vw] flex-col justify-between border-r border-neutral-200/80 bg-[#F9F9F9] shadow-2xl transition-transform duration-250 ease-[cubic-bezier(0.32,0.72,0,1)] select-none ${
            mobileOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
        >
          <SidebarBody
            user={user}
            onClose={() => onMobileOpenChange(false)}
            isMobile={true}
          />
        </aside>
      </div>
    </>
  )
}

function SidebarBody({
  user,
  onClose,
  isMobile,
}: {
  user: AuthUser
  onClose: () => void
  isMobile: boolean
}) {
  const { data: incidents } = useIncidentList()
  const location = useLocation()
  const queryClient = useQueryClient()

  const logoutMutation = useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      queryClient.setQueryData(queryKeys.auth.status(), {
        initialized: true,
        authenticated: false,
        user: null,
      })
      queryClient.removeQueries({ queryKey: queryKeys.incidents.all })
      queryClient.removeQueries({ queryKey: queryKeys.runbooks.all })
      queryClient.removeQueries({ queryKey: queryKeys.settings.all })
    },
  })

  const recentIncidents = (incidents ?? []).slice(0, 10)

  const activeNav = location.pathname.startsWith('/runbooks')
    ? '/runbooks'
    : location.pathname.startsWith('/integrations')
      ? '/integrations'
      : location.pathname.startsWith('/settings')
        ? '/settings'
        : location.pathname === '/incidents'
          ? '/incidents'
          : location.pathname === '/dashboard'
            ? '/dashboard'
            : null

  const initials = user.name
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  return (
    <>
      <div className="flex min-h-0 w-full flex-1 flex-col px-3 pt-4">
        {/* Top Brand & Collapse/Close Row */}
        <div className="flex items-center justify-between px-2 pb-4">
          <Link
            to="/dashboard"
            className="focus-visible:outline-none"
          >
            <BrandLogo />
          </Link>

          <button
            type="button"
            onClick={onClose}
            title={isMobile ? 'Close menu' : 'Collapse sidebar'}
            aria-label={isMobile ? 'Close menu' : 'Collapse sidebar'}
            className="flex size-8 cursor-pointer items-center justify-center rounded-lg text-neutral-500 transition-colors duration-100 hover:bg-neutral-200/60 hover:text-neutral-900"
          >
            {isMobile ? (
              <X className="size-[18px]" strokeWidth={1.75} />
            ) : (
              <PanelLeft className="size-[17px]" strokeWidth={1.75} />
            )}
          </button>
        </div>

        {/* Primary Navigation Items */}
        <nav className="space-y-0.5" aria-label="Main navigation">
          {MAIN_NAV_ITEMS.map((item) => {
            const active = activeNav === item.to
            const Icon = item.icon

            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={`flex h-10 items-center gap-3 rounded-full px-3.5 text-[14px] transition-colors duration-100 focus-visible:outline-none ${
                  active
                    ? 'bg-neutral-200/75 font-medium text-neutral-950'
                    : 'font-normal text-neutral-700 hover:bg-neutral-200/45 hover:text-neutral-950'
                }`}
              >
                <Icon
                  active={active}
                  className={`size-[18px] shrink-0 transition-colors duration-100 ${
                    active ? 'text-neutral-950' : 'text-neutral-600'
                  }`}
                />
                <span>{item.label}</span>
              </NavLink>
            )
          })}
        </nav>

        {/* Recent Incidents History */}
        <div className="mt-7 flex min-h-0 flex-1 flex-col">
          <div className="mb-1.5 flex items-center justify-between px-3.5">
            <span className="text-[12px] font-medium text-neutral-400">
              Recent incidents
            </span>
          </div>

          {recentIncidents.length === 0 ? (
            <p className="px-3.5 py-2 text-[13.5px] text-neutral-400">
              No incidents yet
            </p>
          ) : (
            <div className="space-y-0.5 overflow-y-auto pr-0.5">
              {recentIncidents.map((incident) => {
                const targetPath = `/incidents/${incident.id}/live`
                const isCurrent = location.pathname === targetPath
                const isRunning =
                  incident.status === 'PENDING' || incident.status === 'TRIAGING'

                return (
                  <Link
                    key={incident.id}
                    to={targetPath}
                    className={`flex h-9 items-center justify-between gap-2 rounded-full px-3.5 text-[13.5px] transition-colors duration-100 ${
                      isCurrent
                        ? 'bg-neutral-200/75 font-medium text-neutral-950'
                        : 'font-normal text-neutral-700 hover:bg-neutral-200/45 hover:text-neutral-950'
                    }`}
                  >
                    <span className="truncate">{incident.title}</span>

                    {isRunning && (
                      <span className="shrink-0 rounded-md bg-amber-100/90 px-1.5 py-0.5 text-[11px] font-medium text-amber-800">
                        live
                      </span>
                    )}
                  </Link>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Bottom User Bar */}
      <div className="w-full px-3 py-3">
        <div className="flex items-center justify-between gap-2 rounded-xl px-2 py-1.5">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-neutral-900 text-xs font-medium text-white">
              {initials || 'U'}
            </span>
            <span className="truncate text-[14px] font-medium text-neutral-800">
              {user.name}
            </span>
          </div>

          <button
            type="button"
            onClick={() => logoutMutation.mutate()}
            disabled={logoutMutation.isPending}
            title="Sign out"
            aria-label="Sign out"
            className="flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-lg text-neutral-500 transition-colors duration-100 hover:bg-neutral-200/60 hover:text-neutral-900"
          >
            <LogOut className="size-[16px]" strokeWidth={1.75} />
          </button>
        </div>
      </div>
    </>
  )
}
