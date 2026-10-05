import type { IncidentSummary } from '../../../shared/types/incident'
import { StatusBadge } from '../../../shared/components/status-badge'
import { TimeAgo } from '../../../shared/components/time-ago'

interface IncidentRowProps {
  incident: IncidentSummary
  onOpen: (incident: IncidentSummary) => void
}

export function IncidentRow({ incident, onOpen }: IncidentRowProps) {
  return (
    <button
      type="button"
      onClick={() => onOpen(incident)}
      className="group flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition-colors hover:bg-neutral-50"
    >
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-neutral-900">{incident.title}</p>
        <p className="mt-0.5 text-xs text-neutral-500">
          <TimeAgo date={incident.created_at} />
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <StatusBadge status={incident.status} />
        <svg
          className="size-4 text-neutral-300 transition-colors group-hover:text-neutral-500"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
          aria-hidden
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
        </svg>
      </div>
    </button>
  )
}
