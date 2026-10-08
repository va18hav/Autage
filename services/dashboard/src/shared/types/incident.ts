export type IncidentStatus = 'PENDING' | 'TRIAGING' | 'COMPLETED' | 'FAILED'
export type StepStatus = 'RUNNING' | 'COMPLETED' | 'FAILED'

export interface IncidentStep {
  id: string
  incident_id: string
  step_name: string
  status: StepStatus
  input_data: Record<string, unknown> | null
  output_data: Record<string, unknown> | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface IncidentSummary {
  id: string
  title: string
  status: IncidentStatus
  fingerprint: string | null
  created_at: string
  updated_at: string
}

export interface ContextSummary {
  affected_pods: string[]
  root_cause_hypothesis: string
  key_signals: string[]
  recommended_next_steps: string[]
}

export interface IncidentDetail extends IncidentSummary {
  raw_alert: Record<string, unknown>
  // string = legacy proposed_action; string[] = context_summary.recommended_next_steps
  recommended_steps: Record<string, unknown> | string | string[] | null
  steps: IncidentStep[]
}

export type SseEvent =
  | { type: 'status'; status: string }
  | {
      type: 'step_complete'
      node: string
      data: Record<string, unknown> & {
        context_summary?: ContextSummary
        recommended_action?: string
      }
    }
  | { type: 'incident_complete'; status: string; title?: string; recommended_steps?: unknown }
  | { type: 'incident_failed'; status: string; error?: string }
