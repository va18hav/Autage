import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import type { IncidentSummary } from '../../../shared/types/incident'
import { IncidentRow } from './incident-row'

interface RecentIncidentsCardProps {
  incidents: IncidentSummary[]
  onSelect: (incident: IncidentSummary) => void
}

export function RecentIncidentsCard({ incidents, onSelect }: RecentIncidentsCardProps) {
  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-[17px] font-semibold tracking-tight text-neutral-900">
          Recent Incidents
        </h2>
        <Link
          to="/incidents"
          className="inline-flex items-center gap-1.5 text-[14px] font-medium text-neutral-600 transition-colors hover:text-neutral-950"
        >
          <span>View all</span>
          <ArrowRight className="size-4" />
        </Link>
      </div>

      {incidents.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-neutral-200 bg-neutral-50/40 px-6 py-14 text-center">
          <p className="text-[15px] font-medium text-neutral-800">
            No incidents recorded yet
          </p>
          <p className="mt-1 text-[14px] text-neutral-500">
            Configure your monitoring webhook in Integrations to begin receiving alerts.
          </p>
        </div>
      ) : (
        <div className="divide-y divide-neutral-100 overflow-hidden rounded-2xl border border-neutral-200/80 bg-white">
          {incidents.slice(0, 5).map((incident) => (
            <IncidentRow
              key={incident.id}
              incident={incident}
              onOpen={onSelect}
            />
          ))}
        </div>
      )}
    </section>
  )
}
