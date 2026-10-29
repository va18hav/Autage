export type IncidentStatus = 'PENDING' | 'TRIAGING' | 'COMPLETED' | 'FAILED'
export type StepStatus = 'RUNNING' | 'COMPLETED' | 'FAILED'
export type IncidentType = 'crash_loop' | 'bad_deployment' | 'other'
export type Confidence = 'low' | 'medium' | 'high'

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
  incident_type: IncidentType | null
  created_at: string
  updated_at: string
}

export interface Diagnosis {
  what_happened: string
  likely_cause: string
  confidence: Confidence
  what_i_found: string
  missing_information: string[]
  recommended_steps: string[]
}

export interface IncidentDetail extends IncidentSummary {
  raw_alert: Record<string, unknown>
  analysis: Diagnosis | null
  // Temporary compatibility field: older incidents only have this shape.
  recommended_steps: Record<string, unknown> | string | string[] | null
  steps: IncidentStep[]
}

export type SseEvent =
  | { type: 'status'; status: string }
  | {
      type: 'step_complete'
      node: string
      data: Record<string, unknown>
    }
  | {
      type: 'incident_complete'
      status: string
      title?: string
      incident_type?: IncidentType | null
      analysis?: Diagnosis | null
      recommended_steps?: unknown
    }
  | { type: 'incident_failed'; status: string; error?: string }
