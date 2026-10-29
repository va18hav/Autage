import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useIncidentDetail } from '../../dashboard/hooks/use-incident-detail'
import { incidentApi, streamIncident } from '../../../shared/lib/api'
import { queryKeys } from '../../../shared/lib/query-client'
import { useIncidentLiveStore } from '../store/incident-live-store'
import type { IncidentStatus } from '../../../shared/types/incident'
import { DeleteIncidentDialog } from '../components/delete-incident-dialog'
import { DiagnosisCard } from '../components/diagnosis-card'
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
      incidentType: incident.incident_type,
      steps: incident.steps.map((s) => ({
        id: s.id,
        name: s.step_name,
        status: s.status,
        output_data: s.output_data,
        input_data: s.input_data,
        error_message: s.error_message,
      })),
      analysis: incident.analysis,
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
  const analysis = useIncidentLiveStore((s) => s.analysis)
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

      {analysis && <DiagnosisCard diagnosis={analysis} />}

      <LiveTerminal steps={steps} live={live} />

      {errorMessage && (
        <p className="rounded-2xl border border-red-200/80 bg-red-50/60 px-5 py-4 text-[14px] text-red-700">
          {errorMessage}
        </p>
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
