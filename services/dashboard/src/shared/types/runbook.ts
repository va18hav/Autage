export interface RunbookSectionCreate {
  heading: string
  content: string
  order_index: number
}

export interface RunbookCreate {
  title: string
  description: string | null
  service: string | null
  triggers: string[] | null
  raw_content: string
  sections: RunbookSectionCreate[]
}

export interface RunbookSection {
  id: string
  runbook_id: string
  order_index: number
  heading: string
  content: string
  created_at: string
  updated_at: string
}

export interface RunbookSummary {
  id: string
  title: string
  description: string | null
  service: string | null
  created_at: string
  updated_at: string
}

export interface RunbookDetail extends RunbookSummary {
  triggers: string[] | null
  raw_content: string
  sections: RunbookSection[]
}
