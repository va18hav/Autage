import { create } from 'zustand'
import type { ContextSummary, SseEvent, StepStatus } from '../../../shared/types/incident'

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
  status: string
  steps: LiveStep[]
  contextSummary: ContextSummary | null
  recommendedNextSteps: string[] | null
  errorMessage: string | null
  isComplete: boolean
  applyEvent: (event: SseEvent) => void
  hydrate: (payload: {
    title: string
    status: string
    steps: LiveStep[]
    contextSummary: ContextSummary | null
    recommendedNextSteps: string[] | null
  }) => void
  reset: () => void
}

const INITIAL = {
  incidentTitle: null,
  status: 'PENDING',
  steps: [] as LiveStep[],
  contextSummary: null,
  recommendedNextSteps: null as string[] | null,
  errorMessage: null,
  isComplete: false,
}

// The worker publishes SSE events under the graph node name, while the DB
// step rows use the decorator step_name. Map node names onto their step_name
// so SSE updates and hydrated rows are treated as the same step.
const CANONICAL_NAMES: Record<string, string> = {
  process_alert: 'triage',
  gather_context: 'fetch_logs',
  context_gathering: 'fetch_logs',
}

const canonicalName = (name: string) => CANONICAL_NAMES[name] ?? name

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
          const name = canonicalName(event.node)
          const data = event.data
          const steps = [...state.steps]
          const existing = steps.findIndex((s) => canonicalName(s.name) === name)
          const entry: LiveStep = {
            id: existing >= 0 ? steps[existing].id : `${name}-${steps.length}`,
            name,
            status: 'COMPLETED',
            output_data: data,
          }
          if (existing >= 0) steps[existing] = entry
          else steps.push(entry)

          const contextSummary =
            (data.context_summary as ContextSummary | undefined) ?? state.contextSummary

          return {
            steps,
            contextSummary,
            recommendedNextSteps:
              contextSummary?.recommended_next_steps ?? state.recommendedNextSteps,
          }
        }
        case 'incident_complete': {
          const published = event.recommended_steps
          const nextSteps = Array.isArray(published)
            ? (published as string[])
            : state.recommendedNextSteps

          return {
            status:
              INCIDENT_STATUS_RANK[event.status] > INCIDENT_STATUS_RANK[state.status]
                ? event.status
                : state.status,
            incidentTitle: event.title ?? state.incidentTitle,
            recommendedNextSteps: nextSteps,
            isComplete: true,
          }
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
      const rowsByName = new Map<string, LiveStep>()
      for (const step of payload.steps) {
        rowsByName.set(canonicalName(step.name), step)
      }

      // Hydrated DB rows are the base (they carry ids / timestamps); live SSE
      // steps are merged in per canonical name, keeping whichever has the more
      // progressed status so stale REST data can't undo a completed step.
      const rowsByCanonical = new Map<string, LiveStep>()
      for (const [name, row] of rowsByName) {
        const prev = rowsByCanonical.get(name)
        if (!prev || STATUS_RANK[row.status] > STATUS_RANK[prev.status]) {
          rowsByCanonical.set(name, row)
        }
      }

      const liveByName = new Map<string, LiveStep>()
      for (const step of state.steps) {
        const name = canonicalName(step.name)
        const prev = liveByName.get(name)
        if (!prev || STATUS_RANK[step.status] > STATUS_RANK[prev.status]) {
          liveByName.set(name, step)
        }
      }

      const steps: LiveStep[] = []
      for (const [name, row] of rowsByCanonical) {
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
      // SSE-only steps (e.g. route_pX) that have no DB row yet keep their position
      for (const [, step] of liveByName) steps.push(step)

      return {
        incidentTitle: state.incidentTitle ?? payload.title,
        status:
        INCIDENT_STATUS_RANK[payload.status] > INCIDENT_STATUS_RANK[state.status]
          ? payload.status
          : state.status,
        steps,
        contextSummary: state.contextSummary ?? payload.contextSummary,
        recommendedNextSteps: state.recommendedNextSteps ?? payload.recommendedNextSteps,
      }
    }),
  reset: () => set({ ...INITIAL }),
}))
