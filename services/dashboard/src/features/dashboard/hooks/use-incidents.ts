import { useQuery } from '@tanstack/react-query'
import { incidentApi } from '../../../shared/lib/api'
import { queryKeys } from '../../../shared/lib/query-client'

export function useIncidentList() {
  return useQuery({
    queryKey: queryKeys.incidents.lists(),
    queryFn: incidentApi.list,
    refetchInterval: 10_000,
  })
}
