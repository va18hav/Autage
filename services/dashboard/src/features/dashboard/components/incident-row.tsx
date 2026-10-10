import { Link, useNavigate } from 'react-router-dom'
import { ArrowUpRight, ChevronRight } from 'lucide-react'
import type { IncidentSummary } from '../../../shared/types/incident'
import { StatusBadge } from '../../../shared/components/status-badge'
import { TimeAgo } from '../../../shared/components/time-ago'

interface IncidentRowProps {
  incident: IncidentSummary
  onOpen: (incident: IncidentSummary) => void
}

export function IncidentRow({ incident, onOpen }: IncidentRowProps) {
  const navigate = useNavigate()
  const isOngoing = incident.status === 'PENDING' || incident.status === 'TRIAGING'

  const handleOpen = () => {
    if (typeof window !== 'undefined' && window.matchMedia('(max-width: 767px)').matches) {
      navigate(`/incidents/${incident.id}/live`)
      return
    }
    onOpen(incident)
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleOpen}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          handleOpen()
        }
      }}
      className="group flex w-full cursor-pointer flex-col items-start justify-between gap-3 px-4 py-4 text-left transition-colors duration-100 hover:bg-neutral-50/90 focus-visible:bg-neutral-50/90 focus-visible:outline-none sm:flex-row sm:items-center sm:gap-4 sm:px-6"
    >
      <div className="min-w-0 w-full flex-1">
        <p className="line-clamp-2 text-[15px] font-medium leading-snug text-neutral-900 group-hover:text-neutral-950 sm:truncate">
          {incident.title}
        </p>
        <p className="mt-1 text-[13px] text-neutral-500">
          Opened <TimeAgo date={incident.created_at} />
        </p>
      </div>

      <div className="flex w-full shrink-0 items-center justify-between gap-2.5 sm:w-auto sm:justify-end sm:gap-3">
        <div className="flex items-center gap-2">
          {isOngoing && (
            <Link
              to={`/incidents/${incident.id}/live`}
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1.5 rounded-full border border-neutral-200 bg-white px-3.5 py-1.5 text-[13px] font-medium whitespace-nowrap text-neutral-800 transition-colors duration-100 hover:border-neutral-300 hover:bg-neutral-50"
            >
              <span>Live stream</span>
              <ArrowUpRight className="size-3.5 text-neutral-500" />
            </Link>
          )}

          <StatusBadge status={incident.status} />
        </div>

        <ChevronRight className="size-4 shrink-0 text-neutral-300 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-neutral-600" />
      </div>
    </div>
  )
}
