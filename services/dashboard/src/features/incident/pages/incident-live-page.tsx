import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useIncidentDetail } from '../../dashboard/hooks/use-incident-detail'
import { streamIncident } from '../../../shared/lib/api'
import { queryKeys } from '../../../shared/lib/query-client'
import { useIncidentLiveStore } from '../store/incident-live-store'
import type { ContextSummary, IncidentStatus } from '../../../shared/types/incident'
import { ContextSummaryCard } from '../components/context-summary'
import { LiveHeader } from '../components/live-header'
import { LiveTerminal } from '../components/live-terminal'

export function IncidentLivePage() {
  const { incidentId } = useParams<{ incidentId: string }>()
  const { data: incident } = useIncidentDetail(incidentId ?? '')
  const applyEvent = useIncidentLiveStore((s) => s.applyEvent)
  const hydrate = useIncidentLiveStore((s) => s.hydrate)
  const reset = useIncidentLiveStore((s) => s.reset)

  const queryClient = useQueryClient()

  useEffect(() => {
    reset()
  }, [incidentId, reset])

  // No "hydrate once" guard here: hydrate() is merge-based and idempotent, so
  // refetches (e.g. after the SSE stream ends) can safely re-sync fresh status
  // without overwriting live SSE completions.
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
  const errorMessage = useIncidentLiveStore((s) => s.errorMessage)
  const incidentTitle = useIncidentLiveStore((s) => s.incidentTitle)

  const live = !isComplete && status !== 'COMPLETED' && status !== 'FAILED'

  return (
    <div className="space-y-6">
      <LiveHeader
        title={incidentTitle ?? incident?.title ?? 'Incident'}
        status={status as IncidentStatus}
      />

      {/* Steps get the full content width on their own */}
      <LiveTerminal steps={steps} live={live} />

      {/* Findings below the step timeline */}
      {(contextSummary || errorMessage) && (
        <div className="grid gap-6 md:grid-cols-2">
          {contextSummary && <ContextSummaryCard data={contextSummary} />}
          {errorMessage && (
            <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 md:col-span-2">
              {errorMessage}
            </p>
          )}
        </div>
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
