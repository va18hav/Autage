import {
  NavDashboardIcon,
  NavIncidentsIcon,
  NavIntegrationsIcon,
  NavRunbooksIcon,
  NavSettingsIcon,
} from '../components/icons'

export const MAIN_NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: NavDashboardIcon },
  { to: '/incidents', label: 'Incidents', icon: NavIncidentsIcon },
  { to: '/runbooks', label: 'Runbooks', icon: NavRunbooksIcon },
  { to: '/integrations', label: 'Integrations', icon: NavIntegrationsIcon },
  { to: '/settings', label: 'Settings', icon: NavSettingsIcon },
] as const
