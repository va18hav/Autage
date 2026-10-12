import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useIncidentDetail } from '../../dashboard/hooks/use-incident-detail'
import { incidentApi, streamIncident } from '../../../shared/lib/api'
import { queryKeys } from '../../../shared/lib/query-client'
import { useIncidentLiveStore } from '../store/incident-live-store'
import type { ContextSummary, IncidentStatus } from '../../../shared/types/incident'
import { ContextSummaryCard } from '../components/context-summary'
import { DeleteIncidentDialog } from '../components/delete-incident-dialog'
import { LiveHeader } from '../components/live-header'
import { LiveTerminal } from '../components/live-terminal'

export function IncidentLivePage() {
  const { incidentId } = useParams<{ incidentId: string }>()
  const navigate = useNavigate()
  const { data: incident } = useIncidentDetail(incidentId ?? '')
  const applyEvent = useIncidentLiveStore((s) => s.applyEvent)
  const hydrate = useIncidentLiveStore((s) => s.hydrate)
  const reset = useIncidentLiveStore((s) => s.reset)

  const queryClient = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: () => incidentApi.delete(incidentId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.incidents.all })
      navigate('/incidents')
    },
  })

  useEffect(() => {
    reset()
  }, [incidentId, reset])

  useEffect(() => {
    if (!incident) return
    hydrate({
      title: incident.title,
      status: incident.status,
      steps: incident.steps.map((s) => ({
        id: s.id,
        name: s.step_name,
        status: s.status,
        output_data: s.output_data,
        input_data: s.input_data,
        error_message: s.error_message,
      })),
      contextSummary: extractContextSummary(incident),
      recommendedNextSteps: extractRecommendedNextSteps(incident),
    })
  }, [incident, hydrate])

  useEffect(() => {
    if (!incidentId) return

    const unsubscribe = streamIncident(incidentId, applyEvent, () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.incidents.all })
    })

    return unsubscribe
  }, [incidentId, applyEvent, queryClient])

  const status = useIncidentLiveStore((s) => s.status)
  const steps = useIncidentLiveStore((s) => s.steps)
  const isComplete = useIncidentLiveStore((s) => s.isComplete)
  const contextSummary = useIncidentLiveStore((s) => s.contextSummary)
  const recommendedNextSteps = useIncidentLiveStore((s) => s.recommendedNextSteps)
  const errorMessage = useIncidentLiveStore((s) => s.errorMessage)
  const incidentTitle = useIncidentLiveStore((s) => s.incidentTitle)

  const live = !isComplete && status !== 'COMPLETED' && status !== 'FAILED'

  return (
    <div className="space-y-7">
      <LiveHeader
        title={incidentTitle ?? incident?.title ?? 'Incident'}
        status={status as IncidentStatus}
        incidentId={incidentId}
      />

      {recommendedNextSteps && recommendedNextSteps.length > 0 && (
        <section className="rounded-2xl border border-neutral-200/80 bg-neutral-50/50 p-5 sm:p-6">
          <h2 className="mb-3 text-[15.5px] font-semibold text-neutral-900">
            Recommended Remediation
          </h2>
          <ol className="divide-y divide-neutral-200/60">
            {recommendedNextSteps.map((step, i) => (
              <li
                key={i}
                className="flex items-start gap-3.5 py-3 first:pt-0 last:pb-0 text-[14.5px] leading-relaxed text-neutral-800"
              >
                <span className="mt-0.5 shrink-0 font-medium text-neutral-400 tabular-nums">
                  {i + 1}.
                </span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </section>
      )}

      <LiveTerminal steps={steps} live={live} />

      {(contextSummary || errorMessage) && (
        <div className="grid gap-6 md:grid-cols-2">
          {contextSummary && <ContextSummaryCard data={contextSummary} />}
          {errorMessage && (
            <p className="rounded-2xl border border-red-200/80 bg-red-50/60 px-5 py-4 text-[14px] text-red-700 md:col-span-2">
              {errorMessage}
            </p>
          )}
        </div>
      )}

      {incidentId && (
        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-neutral-100 pt-5">
          <span className="truncate font-mono text-xs text-neutral-400">{incidentId}</span>
          <DeleteIncidentDialog
            onConfirm={() => deleteMutation.mutate()}
            pending={deleteMutation.isPending}
          />
        </footer>
      )}
    </div>
  )
}

function extractContextSummary(incident: NonNullable<ReturnType<typeof useIncidentDetail>['data']>) {
  const raw = incident.recommended_steps
  if (
    raw &&
    typeof raw === 'object' &&
    'root_cause_hypothesis' in raw &&
    'key_signals' in raw
  ) {
    return raw as unknown as ContextSummary
  }
  return null
}

function extractRecommendedNextSteps(
  incident: NonNullable<ReturnType<typeof useIncidentDetail>['data']>,
): string[] | null {
  const persisted = incident.recommended_steps
  if (Array.isArray(persisted) && persisted.every((s) => typeof s === 'string')) {
    return persisted
  }

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
