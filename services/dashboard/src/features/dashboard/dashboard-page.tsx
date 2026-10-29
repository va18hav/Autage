import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { useIncidentList } from './hooks/use-incidents'
import { useRunbooksList } from '../runbooks/hooks/use-runbooks'
import { llmSettingsApi, providerApi, webhookSettingsApi } from '../../shared/lib/api'
import { queryKeys } from '../../shared/lib/query-client'
import type { IncidentSummary } from '../../shared/types/incident'
import { IncidentDetailSheet } from '../incident/components/incident-detail-sheet'
import { ActiveTriageBanner } from './components/active-triage-banner'
import { IncidentActivityCard } from './components/incident-activity-card'
import { IntegrationsBentoCard } from './components/integrations-bento-card'
import { PipelineTopologyCard } from './components/pipeline-topology-card'
import { RecentIncidentsCard } from './components/recent-incidents-card'

const ONGOING: IncidentSummary['status'][] = ['PENDING', 'TRIAGING']

export function DashboardPage() {
  const { data: incidents } = useIncidentList()
  const { data: runbooks } = useRunbooksList()
  const { data: catalog } = useQuery({
    queryKey: queryKeys.settings.catalog(),
    queryFn: providerApi.catalog,
  })
  const { data: llmSettings } = useQuery({
    queryKey: queryKeys.settings.llm(),
    queryFn: llmSettingsApi.get,
  })
  const { data: webhook } = useQuery({
    queryKey: queryKeys.settings.webhook(),
    queryFn: webhookSettingsApi.get,
  })

  const [selectedId, setSelectedId] = useState<string | null>(null)

  const ongoing = useMemo(
    () => (incidents ?? []).filter((i) => ONGOING.includes(i.status)),
    [incidents],
  )

  const configuredProviders = useMemo(
    () => (catalog?.providers ?? []).filter((p) => p.credential_configured),
    [catalog],
  )

  return (
    <div className="space-y-9">
      <header>
        <h1 className="text-[26px] font-semibold tracking-tight text-neutral-900">
          Dashboard
        </h1>
        <p className="mt-1.5 text-[15px] text-neutral-500">
          Live operational telemetry, autonomous pipeline routing, and recent cluster incidents.
        </p>
      </header>

      <ActiveTriageBanner incidents={ongoing} />

      {/* Top Bento Grid: 14-Day Activity Chart + Connected Stack */}
      <div className="grid gap-5 lg:grid-cols-3">
        <IncidentActivityCard incidents={incidents ?? []} />
        <IntegrationsBentoCard
          configuredProviders={configuredProviders}
          webhookConfigured={Boolean(webhook?.configured)}
          runbookCount={runbooks?.length ?? 0}
        />
      </div>

      {/* Model-backed pipeline stages (triage + diagnosis) */}
      <PipelineTopologyCard
        steps={llmSettings?.steps ?? []}
        stepKeys={catalog?.steps ?? []}
        providers={catalog?.providers ?? []}
      />

      {/* Recent Incidents Stream */}
      <RecentIncidentsCard
        incidents={incidents ?? []}
        onSelect={(incident) => setSelectedId(incident.id)}
      />

      <IncidentDetailSheet
        incidentId={selectedId}
        onClose={() => setSelectedId(null)}
      />
    </div>
  )
}
