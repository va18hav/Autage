import { useQuery } from '@tanstack/react-query'
import { incidentApi } from '../../../shared/lib/api'
import { queryKeys } from '../../../shared/lib/query-client'

export function useIncidentDetail(id: string) {
  return useQuery({
    queryKey: queryKeys.incidents.detail(id),
    queryFn: () => incidentApi.detail(id),
    enabled: Boolean(id),
  })
}
