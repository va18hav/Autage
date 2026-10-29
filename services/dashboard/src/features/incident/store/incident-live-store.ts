import { create } from 'zustand'
import type {
  Diagnosis,
  IncidentType,
  SseEvent,
  StepStatus,
} from '../../../shared/types/incident'

export interface LiveStep {
  id: string
  name: string
  status: StepStatus
  output_data?: Record<string, unknown> | null
  input_data?: Record<string, unknown> | null
  error_message?: string | null
}

interface IncidentLiveState {
  incidentTitle: string | null
  incidentType: IncidentType | null
  status: string
  steps: LiveStep[]
  analysis: Diagnosis | null
  errorMessage: string | null
  isComplete: boolean
  applyEvent: (event: SseEvent) => void
  hydrate: (payload: {
    title: string
    status: string
    incidentType: IncidentType | null
    steps: LiveStep[]
    analysis: Diagnosis | null
  }) => void
  reset: () => void
}

const INITIAL = {
  incidentTitle: null,
  incidentType: null as IncidentType | null,
  status: 'PENDING',
  steps: [] as LiveStep[],
  analysis: null as Diagnosis | null,
  errorMessage: null,
  isComplete: false,
}

const CONFIDENCE_VALUES = new Set(['low', 'medium', 'high'])

function asIncidentType(value: unknown): IncidentType | null {
  return value === 'crash_loop' || value === 'bad_deployment' || value === 'other'
    ? value
    : null
}

function isDiagnosis(value: unknown): value is Diagnosis {
  if (!value || typeof value !== 'object') return false
  const diagnosis = value as Record<string, unknown>

  return (
    typeof diagnosis.what_happened === 'string' &&
    typeof diagnosis.likely_cause === 'string' &&
    typeof diagnosis.confidence === 'string' &&
    CONFIDENCE_VALUES.has(diagnosis.confidence) &&
    typeof diagnosis.what_i_found === 'string' &&
    Array.isArray(diagnosis.missing_information) &&
    diagnosis.missing_information.every((item) => typeof item === 'string') &&
    Array.isArray(diagnosis.recommended_steps) &&
    diagnosis.recommended_steps.every((item) => typeof item === 'string')
  )
}

// Higher = further progressed. Used when merging a (possibly stale) hydrated
// row with a live SSE step so a refetch can never downgrade COMPLETED → RUNNING.
const STATUS_RANK: Record<StepStatus, number> = {
  RUNNING: 1,
  COMPLETED: 2,
  FAILED: 3,
}

const INCIDENT_STATUS_RANK: Record<string, number> = {
  PENDING: 0,
  TRIAGING: 1,
  COMPLETED: 2,
  FAILED: 3,
}

export const useIncidentLiveStore = create<IncidentLiveState>((set) => ({
  ...INITIAL,
  applyEvent: (event) =>
    set((state) => {
      switch (event.type) {
        case 'status':
          return {
            status:
              INCIDENT_STATUS_RANK[event.status] > INCIDENT_STATUS_RANK[state.status]
                ? event.status
                : state.status,
          }
        case 'step_complete': {
          const name = event.node
          const data = event.data
          const steps = [...state.steps]
          const existing = steps.findIndex((s) => s.name === name)
          const entry: LiveStep = {
            id: existing >= 0 ? steps[existing].id : `${name}-${steps.length}`,
            name,
            status: 'COMPLETED',
            output_data: data,
          }
          if (existing >= 0) steps[existing] = entry
          else steps.push(entry)

          const diagnosis = data.diagnosis
          const incidentType =
            name === 'triage' ? asIncidentType(data.incident_type) : null

          return {
            steps,
            incidentType: incidentType ?? state.incidentType,
            analysis:
              name === 'diagnose' && isDiagnosis(diagnosis) ? diagnosis : state.analysis,
          }
        }
        case 'incident_complete':
          return {
            status:
              INCIDENT_STATUS_RANK[event.status] > INCIDENT_STATUS_RANK[state.status]
                ? event.status
                : state.status,
            incidentTitle: event.title ?? state.incidentTitle,
            incidentType: event.incident_type ?? state.incidentType,
            analysis:
              event.analysis && isDiagnosis(event.analysis) ? event.analysis : state.analysis,
            isComplete: true,
          }
        case 'incident_failed':
          return {
            status: 'FAILED',
            errorMessage: event.error ?? 'Incident processing failed.',
            isComplete: true,
          }
        default:
          return state
      }
    }),
  hydrate: (payload) =>
    set((state) => {
      // Hydrated DB rows are the base (they carry ids / timestamps); live SSE
      // steps are merged in by name, keeping whichever has the more progressed
      // status so stale REST data can't undo a completed step.
      const rowsByName = new Map<string, LiveStep>()
      for (const row of payload.steps) {
        const prev = rowsByName.get(row.name)
        if (!prev || STATUS_RANK[row.status] > STATUS_RANK[prev.status]) {
          rowsByName.set(row.name, row)
        }
      }

      const liveByName = new Map<string, LiveStep>()
      for (const step of state.steps) {
        const prev = liveByName.get(step.name)
        if (!prev || STATUS_RANK[step.status] > STATUS_RANK[prev.status]) {
          liveByName.set(step.name, step)
        }
      }

      const steps: LiveStep[] = []
      for (const [name, row] of rowsByName) {
        const live = liveByName.get(name)
        liveByName.delete(name)
        if (!live) {
          steps.push(row)
          continue
        }
        const preferLive = STATUS_RANK[live.status] > STATUS_RANK[row.status]
        const source = preferLive ? live : row
        const other = preferLive ? row : live
        steps.push({
          ...source,
          output_data: source.output_data ?? other.output_data,
          input_data: source.input_data ?? other.input_data,
          error_message: source.error_message ?? other.error_message,
        })
      }
      // SSE-only steps (e.g. the currently running node) keep their position.
      for (const [, step] of liveByName) steps.push(step)

      return {
        incidentTitle: state.incidentTitle ?? payload.title,
        incidentType: state.incidentType ?? payload.incidentType,
        status:
          INCIDENT_STATUS_RANK[payload.status] > INCIDENT_STATUS_RANK[state.status]
            ? payload.status
            : state.status,
        steps,
        analysis: state.analysis ?? payload.analysis,
      }
    }),
  reset: () => set({ ...INITIAL }),
}))
