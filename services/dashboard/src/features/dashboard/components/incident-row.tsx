import { ChevronRight } from 'lucide-react'
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
      className="group flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition-colors hover:bg-neutral-50/70 focus-visible:bg-neutral-50/70 focus-visible:outline-none"
    >
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-neutral-900">{incident.title}</p>
        <p className="mt-0.5 flex items-center gap-1.5 text-xs text-neutral-500">
          <TimeAgo date={incident.created_at} />
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <StatusBadge status={incident.status} />
        <ChevronRight className="size-4 text-neutral-300 transition-all group-hover:translate-x-0.5 group-hover:text-neutral-500" />
      </div>
    </button>
  )
}
