import type { SVGProps } from 'react'

export type IconProps = SVGProps<SVGSVGElement> & {
  active?: boolean
}

/**
 * Custom architectural sidebar & pipeline icons — replaces generic Lucide tropes
 * with cohesive 1.6px geometric vector marks that support an active dual-tone state.
 */

export function NavDashboardIcon({ active, className, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      {...props}
    >
      <rect
        x="2.5"
        y="2.5"
        width="6.5"
        height="7.5"
        rx="2"
        fill={active ? 'currentColor' : 'none'}
        fillOpacity={active ? 0.14 : 0}
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <rect
        x="11"
        y="2.5"
        width="6.5"
        height="4.5"
        rx="1.8"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <rect
        x="11"
        y="9"
        width="6.5"
        height="8.5"
        rx="2"
        fill={active ? 'currentColor' : 'none'}
        fillOpacity={active ? 0.14 : 0}
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <rect
        x="2.5"
        y="12"
        width="6.5"
        height="5.5"
        rx="1.8"
        stroke="currentColor"
        strokeWidth="1.6"
      />
    </svg>
  )
}

export function NavIncidentsIcon({ active, className, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      {...props}
    >
      <circle
        cx="10"
        cy="10"
        r="7.25"
        fill={active ? 'currentColor' : 'none'}
        fillOpacity={active ? 0.1 : 0}
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path
        d="M10 6.2V10.4"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
      <circle cx="10" cy="13.4" r="1" fill="currentColor" />
    </svg>
  )
}

export function NavRunbooksIcon({ active, className, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      {...props}
    >
      <rect
        x="3.5"
        y="2.5"
        width="13"
        height="15"
        rx="2.5"
        fill={active ? 'currentColor' : 'none'}
        fillOpacity={active ? 0.12 : 0}
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path
        d="M7 6.75H13M7 10H13M7 13.25H10.5"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  )
}

export function NavIntegrationsIcon({ active, className, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      {...props}
    >
      <circle
        cx="6"
        cy="6"
        r="2.75"
        fill={active ? 'currentColor' : 'none'}
        fillOpacity={active ? 0.16 : 0}
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <circle
        cx="14"
        cy="6"
        r="2.75"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <circle
        cx="10"
        cy="14.25"
        r="2.75"
        fill={active ? 'currentColor' : 'none'}
        fillOpacity={active ? 0.16 : 0}
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path
        d="M7.8 8.1L9 11.7M12.2 8.1L11 11.7M8.75 6H11.25"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  )
}

export function NavSettingsIcon({ active, className, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      {...props}
    >
      <path
        d="M10 2.5L16.25 6.1V13.9L10 17.5L3.75 13.9V6.1L10 2.5Z"
        fill={active ? 'currentColor' : 'none'}
        fillOpacity={active ? 0.1 : 0}
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <circle
        cx="10"
        cy="10"
        r="2.5"
        stroke="currentColor"
        strokeWidth="1.6"
      />
    </svg>
  )
}

/* ── Pipeline Stage Icons ──────────────────────────────────────────────────── */

export function StageTriageIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path
        d="M3 4.5H17L11.8 10.6V15.2L8.2 16.8V10.6L3 4.5Z"
        fill="currentColor"
        fillOpacity="0.1"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function StageDiagnosticsIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <rect
        x="2.5"
        y="3.5"
        width="15"
        height="13"
        rx="2.5"
        fill="currentColor"
        fillOpacity="0.08"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path
        d="M6.25 8L8.75 10.25L6.25 12.5M10.5 12.5H13.75"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function StageRunbooksIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path
        d="M4 3.5C4 2.94772 4.44772 2.5 5 2.5H13.5C14.6046 2.5 15.5 3.39543 15.5 4.5V16.5C15.5 17.0523 15.0523 17.5 14.5 17.5H5.5C4.67157 17.5 4 16.8284 4 16V3.5Z"
        fill="currentColor"
        fillOpacity="0.08"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path
        d="M9.5 2.5V8.5L11.5 7L13.5 8.5V2.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M7 12.5H12.5"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  )
}

export function StageRecommendationsIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path
        d="M10 2.5L16 5V9.8C16 13.6 13.45 16.75 10 17.75C6.55 16.75 4 13.6 4 9.8V5L10 2.5Z"
        fill="currentColor"
        fillOpacity="0.1"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M7.5 10.1L9.25 11.85L12.75 8.15"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
