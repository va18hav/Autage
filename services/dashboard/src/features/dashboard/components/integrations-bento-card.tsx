import { Link } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'
import type { Provider } from '../../../shared/types/settings'
import { ProviderLogo } from '../../settings/components/provider-logo'

const SOURCES = [
  { name: 'Datadog', logo: 'https://cdn.simpleicons.org/datadog' },
  { name: 'Prometheus', logo: 'https://cdn.simpleicons.org/prometheus' },
  { name: 'Grafana', logo: 'https://cdn.simpleicons.org/grafana' },
  { name: 'Sentry', logo: 'https://cdn.simpleicons.org/sentry' },
  { name: 'PagerDuty', logo: 'https://cdn.simpleicons.org/pagerduty' },
] as const

interface IntegrationsBentoCardProps {
  configuredProviders: Provider[]
  webhookConfigured: boolean
  runbookCount: number
}

export function IntegrationsBentoCard({
  configuredProviders,
  runbookCount,
}: IntegrationsBentoCardProps) {
  return (
    <div className="flex flex-col justify-between rounded-2xl border border-neutral-200/80 bg-white p-6">
      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <span className="text-[14px] font-medium text-neutral-500">
            Connected Stack
          </span>
          <Link
            to="/integrations"
            className="inline-flex items-center gap-1 text-[13px] font-medium text-neutral-600 transition-colors hover:text-neutral-950"
          >
            <span>Manage</span>
            <ArrowUpRight className="size-3.5" />
          </Link>
        </div>

        {/* AI Providers */}
        <div>
          <p className="text-[13px] text-neutral-400">AI Providers</p>
          {configuredProviders.length > 0 ? (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {configuredProviders.map((p) => (
                <span
                  key={p.id}
                  className="inline-flex items-center gap-2 rounded-full border border-neutral-200/80 bg-neutral-50/70 px-3 py-1.5 text-[13px] font-medium text-neutral-800"
                >
                  <ProviderLogo
                    providerId={p.id}
                    name={p.display_name}
                    className="size-4 border-0 bg-transparent shadow-none"
                    imgClassName="size-4"
                  />
                  <span>{p.display_name}</span>
                </span>
              ))}
            </div>
          ) : (
            <Link
              to="/integrations"
              className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1 text-[13px] font-medium text-amber-800"
            >
              <span>No API keys configured →</span>
            </Link>
          )}
        </div>

        {/* Monitoring Sources */}
        <div>
          <div className="flex items-center justify-between">
            <p className="text-[13px] text-neutral-400">Alert Webhook</p>
          </div>
          <div className="mt-2 flex items-center gap-2">
            {SOURCES.map((s) => (
              <span
                key={s.name}
                title={s.name}
                className="flex size-8 items-center justify-center rounded-full border border-neutral-200/80 bg-neutral-50/60"
              >
                <img
                  src={s.logo}
                  alt={s.name}
                  className="size-4 object-contain"
                  loading="lazy"
                />
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Runbook Index Footer */}
      <div className="mt-6 flex items-center justify-between gap-3 border-t border-neutral-100 pt-4">
        <div className="min-w-0">
          <p className="text-[14px] font-medium text-neutral-900">
            {runbookCount} {runbookCount === 1 ? 'Runbook' : 'Runbooks'} Indexed
          </p>
          <p className="truncate text-[12.5px] text-neutral-400">
            Chunked for agent retrieval
          </p>
        </div>
        <Link
          to="/runbooks"
          className="inline-flex shrink-0 items-center justify-center rounded-full border border-neutral-200 bg-white px-4 py-1.5 text-center text-[13px] font-medium whitespace-nowrap text-neutral-700 transition-colors hover:bg-neutral-50"
        >
          Open library
        </Link>
      </div>
    </div>
  )
}
