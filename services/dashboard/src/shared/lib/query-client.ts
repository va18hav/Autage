import { QueryClient } from '@tanstack/react-query'
import { ApiError } from './api'

export const queryKeys = {
  auth: {
    all: ['auth'] as const,
    status: () => [...queryKeys.auth.all, 'status'] as const,
  },
  incidents: {
    all: ['incidents'] as const,
    lists: () => [...queryKeys.incidents.all, 'list'] as const,
    detail: (id: string) => [...queryKeys.incidents.all, 'detail', id] as const,
  },
  runbooks: {
    all: ['runbooks'] as const,
    lists: () => [...queryKeys.runbooks.all, 'list'] as const,
    detail: (id: string) => [...queryKeys.runbooks.all, 'detail', id] as const,
  },
  settings: {
    all: ['settings'] as const,
    catalog: () => [...queryKeys.settings.all, 'catalog'] as const,
    llm: () => [...queryKeys.settings.all, 'llm'] as const,
    credentials: () => [...queryKeys.settings.all, 'credentials'] as const,
    webhook: () => [...queryKeys.settings.all, 'webhook'] as const,
    kubernetes: () => [...queryKeys.settings.all, 'kubernetes'] as const,
  },
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (failureCount, error) => {
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          return false
        }
        return failureCount < 2
      },
      refetchOnWindowFocus: false,
    },
  },
})
