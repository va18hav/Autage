import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { StatusBadge } from '../../../shared/components/status-badge'
import type { IncidentStatus } from '../../../shared/types/incident'

export function LiveHeader({
  title,
  status,
}: {
  title: string
  status: IncidentStatus
  incidentId?: string
}) {
  const isLive = status === 'PENDING' || status === 'TRIAGING'

  return (
    <header className="space-y-4">
      <Link
        to="/incidents"
        className="inline-flex items-center gap-2 text-[14px] font-medium text-neutral-500 transition-colors hover:text-neutral-900"
      >
        <ArrowLeft className="size-4" />
        <span>Back to Incidents</span>
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <h1 className="text-[24px] font-semibold tracking-tight text-neutral-900">
          {title}
        </h1>

        <div className="flex items-center gap-2.5">
          {isLive && (
            <span className="inline-flex items-center gap-2 rounded-full bg-red-50 px-3 py-1 text-[12.5px] font-medium text-red-700 ring-1 ring-red-200/70">
              <span className="relative flex size-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-500 opacity-75" />
                <span className="relative inline-flex size-2 rounded-full bg-red-500" />
              </span>
              Streaming live
            </span>
          )}
          <StatusBadge status={status} />
        </div>
      </div>
    </header>
  )
}
