import { QueryClient } from '@tanstack/react-query'

export const queryKeys = {
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
  },
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
})
