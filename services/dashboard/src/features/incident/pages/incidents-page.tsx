import { useMemo, useState } from 'react'
import { useIncidentList } from '../../dashboard/hooks/use-incidents'
import { IncidentRow } from '../../dashboard/components/incident-row'
import type { IncidentSummary } from '../../../shared/types/incident'
import { Skeleton } from '@/components/ui'
import {
  IncidentFilterBar,
  type IncidentStatusFilter,
} from '../components/incident-filter-bar'
import { IncidentDetailSheet } from '../components/incident-detail-sheet'

const ONGOING: IncidentSummary['status'][] = ['PENDING', 'TRIAGING']

export function IncidentsPage() {
  const { data: incidents, isPending, isError } = useIncidentList()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<IncidentStatusFilter>('ALL')
  const [searchQuery, setSearchQuery] = useState('')

  const { filtered, stats } = useMemo(() => {
    const all = incidents ?? []
    const ongoingList = all.filter((i) => ONGOING.includes(i.status))
    const completedList = all.filter((i) => i.status === 'COMPLETED')
    const failedList = all.filter((i) => i.status === 'FAILED')

    const q = searchQuery.trim().toLowerCase()
    const matchesSearch = (i: IncidentSummary) =>
      !q ||
      i.title.toLowerCase().includes(q) ||
      i.id.toLowerCase().includes(q) ||
      Boolean(i.fingerprint && i.fingerprint.toLowerCase().includes(q))

    const byStatus = all.filter((i) => {
      if (statusFilter === 'ONGOING') return ONGOING.includes(i.status)
      if (statusFilter === 'COMPLETED') return i.status === 'COMPLETED'
      if (statusFilter === 'FAILED') return i.status === 'FAILED'
      return true
    })

    return {
      filtered: byStatus.filter(matchesSearch),
      stats: {
        total: all.length,
        ongoing: ongoingList.length,
        completed: completedList.length,
        failed: failedList.length,
      },
    }
  }, [incidents, statusFilter, searchQuery])

  const filterTabs = [
    { key: 'ALL' as const, label: 'All', count: stats.total },
    { key: 'ONGOING' as const, label: 'Active', count: stats.ongoing },
    { key: 'COMPLETED' as const, label: 'Analyzed', count: stats.completed },
    ...(stats.failed > 0
      ? [{ key: 'FAILED' as const, label: 'Failed', count: stats.failed }]
      : []),
  ]

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-[26px] font-semibold tracking-tight text-neutral-900">
          Incidents
        </h1>
        <p className="mt-1.5 text-[15px] text-neutral-500">
          Browse and inspect all incoming alerts, diagnostic traces, and structured diagnoses.
        </p>
      </header>

      <IncidentFilterBar
        tabs={filterTabs}
        activeFilter={statusFilter}
        onFilterChange={setStatusFilter}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
      />

      {isPending && (
        <div className="divide-y divide-neutral-100 overflow-hidden rounded-2xl border border-neutral-200/80 bg-white">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-6 py-5">
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-2/5" />
                <Skeleton className="h-3.5 w-24" />
              </div>
              <Skeleton className="h-7 w-24 rounded-full" />
            </div>
          ))}
        </div>
      )}

      {isError && (
        <div className="rounded-2xl border border-red-200/80 bg-red-50/50 px-6 py-4 text-[14px] text-red-700">
          Unable to load incidents. Ensure the backend service is running on port 8000.
        </div>
      )}

      {incidents && (
        <>
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-neutral-200 bg-neutral-50/40 px-6 py-16 text-center">
              <p className="text-[15px] font-medium text-neutral-800">
                {searchQuery || statusFilter !== 'ALL'
                  ? 'No matching incidents'
                  : 'No incidents recorded yet'}
              </p>
              <p className="mt-1.5 max-w-md text-[14px] text-neutral-500">
                {searchQuery || statusFilter !== 'ALL'
                  ? 'Try adjusting your search query or switching filter tabs.'
                  : 'Alerts sent to your webhook endpoint will automatically appear here.'}
              </p>
              {(searchQuery || statusFilter !== 'ALL') && (
                <button
                  type="button"
                  onClick={() => {
                    setSearchQuery('')
                    setStatusFilter('ALL')
                  }}
                  className="mt-4 cursor-pointer rounded-full border border-neutral-200 bg-white px-4 py-2 text-[13.5px] font-medium text-neutral-700 hover:bg-neutral-50"
                >
                  Clear filters
                </button>
              )}
            </div>
          ) : (
            <div className="divide-y divide-neutral-100 overflow-hidden rounded-2xl border border-neutral-200/80 bg-white">
              {filtered.map((incident) => (
                <IncidentRow
                  key={incident.id}
                  incident={incident}
                  onOpen={(i) => setSelectedId(i.id)}
                />
              ))}
            </div>
          )}
        </>
      )}

      <IncidentDetailSheet
        incidentId={selectedId}
        onClose={() => setSelectedId(null)}
      />
    </div>
  )
}
