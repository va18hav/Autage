import { useQuery } from '@tanstack/react-query'
import { authApi } from '../../../shared/lib/api'
import { queryKeys } from '../../../shared/lib/query-client'

export function useAuthStatus() {
  return useQuery({
    queryKey: queryKeys.auth.status(),
    queryFn: authApi.status,
    staleTime: 60_000,
  })
}
