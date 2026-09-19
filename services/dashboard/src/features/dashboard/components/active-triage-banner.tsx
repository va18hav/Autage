import { Link } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'
import type { IncidentSummary } from '../../../shared/types/incident'
import { TimeAgo } from '../../../shared/components/time-ago'

interface ActiveTriageBannerProps {
  incidents: IncidentSummary[]
}

export function ActiveTriageBanner({ incidents }: ActiveTriageBannerProps) {
  if (incidents.length === 0) return null

  return (
    <section className="divide-y divide-neutral-100 overflow-hidden rounded-2xl border border-neutral-200/80 bg-white">
      {incidents.map((incident) => (
        <Link
          key={incident.id}
          to={`/incidents/${incident.id}/live`}
          className="group flex flex-col items-start justify-between gap-3 px-5 py-4 transition-colors duration-100 hover:bg-neutral-50/80 sm:flex-row sm:items-center sm:px-6"
        >
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-3">
            <span className="inline-flex shrink-0 items-center gap-2 rounded-full bg-neutral-100 px-3 py-1 text-[12.5px] font-medium text-neutral-800">
              <span className="relative flex size-2">
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-amber-500 opacity-75" />
                <span className="relative inline-flex size-2 rounded-full bg-amber-500" />
              </span>
              Triaging
            </span>

            <p className="truncate text-[15px] font-medium text-neutral-900">
              {incident.title}
            </p>

            <span className="text-[13px] text-neutral-400">
              <TimeAgo date={incident.created_at} />
            </span>
          </div>

          <span className="inline-flex shrink-0 items-center gap-1.5 text-[13.5px] font-medium text-neutral-600 transition-colors group-hover:text-neutral-950">
            <span>Watch live</span>
            <ArrowUpRight className="size-4 text-neutral-400 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-neutral-900" />
          </span>
        </Link>
      ))}
    </section>
  )
}
