import type { IncidentDetail, IncidentSummary, SseEvent } from '../types/incident'
import type { RunbookCreate, RunbookDetail, RunbookSummary } from '../types/runbook'
import type {
  Credential,
  ProviderCatalog,
  StepConfig,
  StepConfigUpdate,
  TestCredentialResult,
} from '../types/settings'

const BASE_URL = '/api'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })

  if (!response.ok) {
    const detail = await response.text().catch(() => '')
    throw new ApiError(response.status, detail || response.statusText)
  }
  if (response.status === 204) {
    return undefined as unknown as T
  }
  return response.json() as Promise<T>
}

export const incidentApi = {
  list: () => request<IncidentSummary[]>('/incidents'),

  detail: (id: string) => request<IncidentDetail>(`/incidents/${id}`),

  delete: (id: string) => request<void>(`/incidents/${id}`, { method: 'DELETE' }),
}

export const runbookApi = {
  create: (payload: RunbookCreate) =>
    request<RunbookDetail>('/runbooks', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  list: () => request<RunbookSummary[]>('/runbooks'),

  detail: (id: string) => request<RunbookDetail>(`/runbooks/${id}`),

  delete: (id: string) => request<void>(`/runbooks/${id}`, { method: 'DELETE' }),
}

export const providerApi = {
  catalog: () => request<ProviderCatalog>('/settings/providers'),
}

export const llmSettingsApi = {
  get: () => request<{ steps: StepConfig[] }>('/settings/llm'),

  save: (steps: StepConfigUpdate[]) =>
    request<{ steps: StepConfig[] }>('/settings/llm', {
      method: 'PUT',
      body: JSON.stringify(steps),
    }),

  resetStep: (stepKey: string) =>
    request<void>(`/settings/llm/${stepKey}`, { method: 'DELETE' }),
}

export const credentialApi = {
  list: () => request<Credential[]>('/settings/credentials'),

  save: (purpose: string, fields: Record<string, string>) =>
    request<Credential>(`/settings/credentials/${purpose}`, {
      method: 'PUT',
      body: JSON.stringify({ fields }),
    }),

  delete: (purpose: string) =>
    request<void>(`/settings/credentials/${purpose}`, { method: 'DELETE' }),

  test: (purpose: string, fields: Record<string, string>) =>
    request<TestCredentialResult>(`/settings/credentials/${purpose}/test`, {
      method: 'POST',
      body: JSON.stringify({ fields }),
    }),
}

export function streamIncident(
  incidentId: string,
  onEvent: (event: SseEvent) => void,
  onDone: () => void,
): () => void {
  const controller = new AbortController()
  ;(async () => {
    try {
      const response = await fetch(`${BASE_URL}/incidents/${incidentId}/stream`, {
        signal: controller.signal,
      })
      if (!response.ok || !response.body) {
        onDone()
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const blocks = buffer.split('\n\n')
        buffer = blocks.pop() ?? ''

        for (const block of blocks) {
          const dataLines = block
            .split('\n')
            .filter((l) => l.startsWith('data: '))
            .map((l) => l.slice(6))
          if (!dataLines.length) continue
          try {
            onEvent(JSON.parse(dataLines.join('\n')) as SseEvent)
          } catch {
            // malformed frame — skip
          }
        }
      }
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError')) {
        // transient network hiccup — let the caller decide whether to reconnect
      }
    } finally {
      onDone()
    }
  })()

  return () => controller.abort()
}
