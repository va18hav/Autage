import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useIncidentList } from './hooks/use-incidents'
import { useIncidentDetail } from './hooks/use-incident-detail'
import { IncidentRow } from './components/incident-row'
import { StepTimeline } from './components/step-timeline'
import { StatusBadge } from '../../shared/components/status-badge'
import { TimeAgo } from '../../shared/components/time-ago'
import { incidentApi } from '../../shared/lib/api'
import { queryKeys } from '../../shared/lib/query-client'
import type { IncidentSummary } from '../../shared/types/incident'

const ONGOING: IncidentSummary['status'][] = ['PENDING', 'TRIAGING']

export function DashboardPage() {
  const { data: incidents, isPending, isError } = useIncidentList()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { ongoing, past } = useMemo(
    () => ({
      ongoing: (incidents ?? []).filter((i) => ONGOING.includes(i.status)),
      past: (incidents ?? []).filter((i) => !ONGOING.includes(i.status)),
    }),
    [incidents],
  )

  return (
    <div className="space-y-10">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Incidents</h1>
        <p className="mt-1 text-sm text-neutral-500">
          {ongoing.length} ongoing · {past.length} resolved
        </p>
      </header>

      {isPending && (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-xl bg-neutral-200/60" />
          ))}
        </div>
      )}

      {isError && (
        <p className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
          Couldn't load incidents. Is the API running on port 8000?
        </p>
      )}

      {incidents && (
        <>
          <IncidentSection title="Ongoing" count={ongoing.length} isEmpty={ongoing.length === 0}>
            {ongoing.map((incident) => (
              <IncidentRow key={incident.id} incident={incident} onOpen={(i) => setSelectedId(i.id)} />
            ))}
          </IncidentSection>

          <IncidentSection title="Previous" count={past.length} isEmpty={past.length === 0}>
            {past.map((incident) => (
              <IncidentRow key={incident.id} incident={incident} onOpen={(i) => setSelectedId(i.id)} />
            ))}
          </IncidentSection>
        </>
      )}

      {selectedId && <IncidentDrawer id={selectedId} onClose={() => setSelectedId(null)} />}
    </div>
  )
}

function IncidentSection({
  title,
  count,
  isEmpty,
  children,
}: {
  title: string
  count: number
  isEmpty: boolean
  children: React.ReactNode
}) {
  return (
    <section>
      <h2 className="mb-3 text-sm font-medium text-neutral-500">
        {title} · {count}
      </h2>
      {isEmpty ? (
        <p className="rounded-xl border border-dashed border-neutral-200 bg-white px-5 py-8 text-center text-sm text-neutral-400">
          Nothing here
        </p>
      ) : (
        <div className="divide-y divide-neutral-100 overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-[0_1px_2px_rgb(0_0_0/0.04)]">
          {children}
        </div>
      )}
    </section>
  )
}

function IncidentDrawer({ id, onClose }: { id: string; onClose: () => void }) {
  const { data: incident } = useIncidentDetail(id)
  const nextSteps = incident ? extractRecommendedNextSteps(incident) : null
  const queryClient = useQueryClient()
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false)

  const deleteMutation = useMutation({
    mutationFn: () => incidentApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.incidents.all })
      onClose()
    },
  })

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-neutral-950/20 backdrop-blur-[2px]" onClick={onClose} />
      <div className="relative flex h-full w-full max-w-2xl flex-col overflow-hidden border-l bg-white shadow-xl">
        {incident ? (
          <>
            <header className="flex items-start justify-between gap-4 border-b border-neutral-100 px-8 py-6">
              <div className="min-w-0">
                <StatusBadge status={incident.status} />
                <h2 className="mt-3 text-lg font-semibold leading-snug tracking-tight">
                  {incident.title}
                </h2>
                <p className="mt-1 text-xs text-neutral-500">
                  Opened <TimeAgo date={incident.created_at} />
                </p>
              </div>

              <div className="flex items-center gap-2">
                {isConfirmingDelete ? (
                  <div className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-red-50 p-1">
                    <span className="px-1 text-xs font-medium text-red-700">Delete?</span>
                    <button
                      type="button"
                      onClick={() => deleteMutation.mutate()}
                      disabled={deleteMutation.isPending}
                      className="rounded bg-red-600 px-2 py-1 text-xs font-semibold text-white transition-opacity hover:bg-red-700 disabled:opacity-50 cursor-pointer"
                    >
                      {deleteMutation.isPending ? 'Deleting…' : 'Yes'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setIsConfirmingDelete(false)}
                      className="rounded bg-white px-2 py-1 text-xs font-medium text-neutral-600 border border-neutral-200 hover:bg-neutral-100 cursor-pointer"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setIsConfirmingDelete(true)}
                    className="rounded-lg p-1.5 text-neutral-400 transition-colors hover:bg-red-50 hover:text-red-600 cursor-pointer"
                    title="Delete incident"
                    aria-label="Delete incident"
                  >
                    <svg fill="none" viewBox="0 0 24 24" strokeWidth={1.75} stroke="currentColor" className="size-5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
                    </svg>
                  </button>
                )}

                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-lg p-1.5 text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-700 cursor-pointer"
                  aria-label="Close"
                >
                  <svg fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="size-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </header>

            <div
              className="flex-1 space-y-8 overflow-y-auto overscroll-contain px-8 py-6"
              // Composited scrolling for the drawer body
              style={{ willChange: 'scroll-position' }}
            >
              {(incident.status === 'PENDING' || incident.status === 'TRIAGING') && (
                <div className="rounded-xl border border-neutral-200 bg-neutral-50 px-5 py-4">
                  <p className="text-sm font-medium text-neutral-700">Agent still working</p>
                  <p className="mt-1 text-xs text-neutral-500">Watch the triage unfold in real time.</p>
                  <Link
                    to={`/incidents/${incident.id}/live`}
                    className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-neutral-900 underline-offset-4 hover:underline"
                  >
                    Open live view
                    <svg fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="size-4">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12l-7.5 7.5M21 12H9" />
                    </svg>
                  </Link>
                </div>
              )}

              {nextSteps && nextSteps.length > 0 && (
                <section>
                  <h3 className="mb-3 text-sm font-medium text-neutral-500">Recommended steps</h3>
                  <ol className="space-y-1.5">
                    {nextSteps.map((step, i) => (
                      <li key={i} className="flex gap-2 text-sm leading-relaxed text-neutral-700">
                        <span className="shrink-0 font-medium text-neutral-400">{i + 1}.</span>
                        {step}
                      </li>
                    ))}
                  </ol>
                </section>
              )}

              <section>
                <h3 className="mb-3 text-sm font-medium text-neutral-500">Agent steps</h3>
                <StepTimeline steps={incident.steps} />
              </section>
            </div>

            <footer className="flex items-center justify-between border-t border-neutral-100 bg-neutral-50/50 px-8 py-3.5">
              <span className="font-mono text-[11px] text-neutral-400">ID: {incident.id}</span>
              {!isConfirmingDelete && (
                <button
                  type="button"
                  onClick={() => setIsConfirmingDelete(true)}
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-red-600 transition-colors hover:text-red-700 cursor-pointer"
                >
                  <svg fill="none" viewBox="0 0 24 24" strokeWidth={1.75} stroke="currentColor" className="size-4">
                    <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
                  </svg>
                  Delete incident
                </button>
              )}
            </footer>
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center">
            <div className="size-5 animate-spin rounded-full border-2 border-neutral-300 border-t-neutral-700" />
          </div>
        )}
      </div>
    </div>
  )
}

function extractRecommendedNextSteps(incident: NonNullable<ReturnType<typeof useIncidentDetail>['data']>): string[] | null {
  // Preferred source: persisted context_summary.recommended_next_steps
  const persisted = incident.recommended_steps
  if (Array.isArray(persisted) && persisted.every((s) => typeof s === 'string')) {
    return persisted
  }

  // Older incidents: fall back to the context_gathering step output
  for (const step of incident.steps) {
    if (step.step_name !== 'context_gathering' && step.step_name !== 'gather_context') continue
    const next = (step.output_data as { context_summary?: { recommended_next_steps?: unknown } } | null)
      ?.context_summary?.recommended_next_steps
    if (Array.isArray(next) && next.every((s) => typeof s === 'string')) {
      return next as string[]
    }
  }

  return null
}
