import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { runbookApi } from '../../../shared/lib/api'
import { queryKeys } from '../../../shared/lib/query-client'
import type { RunbookCreate } from '../../../shared/types/runbook'

export function useRunbooksList() {
  return useQuery({
    queryKey: queryKeys.runbooks.lists(),
    queryFn: runbookApi.list,
  })
}

export function useRunbookDetail(id: string | null) {
  return useQuery({
    queryKey: id ? queryKeys.runbooks.detail(id) : ['runbooks', 'detail', 'none'],
    queryFn: () => (id ? runbookApi.detail(id) : Promise.reject('No ID')),
    enabled: Boolean(id),
  })
}

export function useCreateRunbook(options?: {
  onSuccess?: () => void
  onError?: (err: unknown) => void
}) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: RunbookCreate) => runbookApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.runbooks.all })
      options?.onSuccess?.()
    },
    onError: options?.onError,
  })
}

export function useDeleteRunbook(options?: {
  onSuccess?: () => void
  onError?: (err: unknown) => void
}) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => runbookApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.runbooks.all })
      options?.onSuccess?.()
    },
    onError: options?.onError,
  })
}
