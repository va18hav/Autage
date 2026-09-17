import type { AuthStatus, AuthUser, LoginPayload, RegisterPayload } from '../types/auth'
import type { IncidentDetail, IncidentSummary, SseEvent } from '../types/incident'
import type { RunbookCreate, RunbookDetail, RunbookSummary } from '../types/runbook'
import type {
  Credential,
  KubernetesConfig,
  KubernetesConfigPayload,
  ProviderCatalog,
  StepConfig,
  StepConfigUpdate,
  TestCredentialResult,
  WebhookSecret,
} from '../types/settings'
import { API_URL } from './config'
import { queryClient, queryKeys } from './query-client'

const BASE_URL = API_URL || '/api'

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
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })

  if (!response.ok) {
    const raw = await response.text().catch(() => '')
    let message = raw || response.statusText
    if (raw) {
      try {
        const parsed = JSON.parse(raw)
        if (typeof parsed?.detail === 'string') {
          message = parsed.detail
        }
      } catch {
        // plain text response
      }
    }

    if (response.status === 401 && !path.startsWith('/auth/')) {
      queryClient.invalidateQueries({ queryKey: queryKeys.auth.status() })
    }

    throw new ApiError(response.status, message)
  }
  if (response.status === 204) {
    return undefined as unknown as T
  }
  return response.json() as Promise<T>
}

export const authApi = {
  status: () => request<AuthStatus>('/auth/status'),

  register: (payload: RegisterPayload) =>
    request<AuthUser>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  login: (payload: LoginPayload) =>
    request<AuthUser>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  logout: () =>
    request<void>('/auth/logout', {
      method: 'POST',
    }),

  me: () => request<AuthUser>('/auth/me'),
}

export const incidentApi = {
  list: () => request<IncidentSummary[]>('/incidents'),

  detail: (id: string) => request<IncidentDetail>(`/incidents/${id}`),

  delete: (id: string) => request<void>(`/incidents/${id}`, { method: 'DELETE' }),

  simulate: (scenario: string) =>
    request<{ incident_id: string; status: string }>('/incidents/simulate', {
      method: 'POST',
      body: JSON.stringify({ scenario }),
    }),
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

export const webhookSettingsApi = {
  get: () => request<WebhookSecret>('/settings/webhook'),

  generateSecret: () =>
    request<WebhookSecret>('/settings/webhook/secret', {
      method: 'POST',
    }),
}

export const kubernetesSettingsApi = {
  get: () => request<KubernetesConfig>('/settings/kubernetes'),

  save: (payload: KubernetesConfigPayload) =>
    request<KubernetesConfig>('/settings/kubernetes', {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  delete: () =>
    request<void>('/settings/kubernetes', {
      method: 'DELETE',
    }),

  test: (payload: KubernetesConfigPayload) =>
    request<TestCredentialResult>('/settings/kubernetes/test', {
      method: 'POST',
      body: JSON.stringify(payload),
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
        credentials: 'include',
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
