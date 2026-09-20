import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Copy, Eye, EyeOff, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'

import { webhookSettingsApi } from '../../../shared/lib/api'
import { WEBHOOK_ALERT_URL } from '../../../shared/lib/config'
import { queryKeys } from '../../../shared/lib/query-client'
import { Button } from '@/components/ui'

const MONITORING_PLATFORMS = [
  {
    id: 'datadog',
    name: 'Datadog',
    logo: 'https://cdn.simpleicons.org/datadog',
  },
  {
    id: 'prometheus',
    name: 'Prometheus',
    logo: 'https://cdn.simpleicons.org/prometheus',
  },
  {
    id: 'grafana',
    name: 'Grafana',
    logo: 'https://cdn.simpleicons.org/grafana',
  },
  {
    id: 'sentry',
    name: 'Sentry',
    logo: 'https://cdn.simpleicons.org/sentry',
  },
  {
    id: 'pagerduty',
    name: 'PagerDuty',
    logo: 'https://cdn.simpleicons.org/pagerduty',
  },
] as const

export function MonitoringSourcesCard() {
  const queryClient = useQueryClient()
  const [revealed, setRevealed] = useState(false)
  const [copiedField, setCopiedField] = useState<'url' | 'secret' | null>(null)

  const webhookQuery = useQuery({
    queryKey: queryKeys.settings.webhook(),
    queryFn: webhookSettingsApi.get,
  })

  const generateMutation = useMutation({
    mutationFn: webhookSettingsApi.generateSecret,
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.settings.webhook(), data)
      setRevealed(true)
      toast.success('Webhook secret generated', {
        description: 'Encrypted and saved to the credentials table.',
      })
    },
    onError: (err) => {
      toast.error('Failed to generate webhook secret', {
        description: err instanceof Error ? err.message : 'Unknown error',
      })
    },
  })

  const endpointUrl = WEBHOOK_ALERT_URL

  const copyText = (value: string, field: 'url' | 'secret') => {
    navigator.clipboard.writeText(value)
    setCopiedField(field)
    setTimeout(() => setCopiedField(null), 1500)
  }

  if (webhookQuery.isLoading) {
    return (
      <div className="h-44 animate-pulse rounded-lg border border-border/80 bg-white p-6" />
    )
  }

  const webhook = webhookQuery.data
  const isConfigured = Boolean(webhook?.configured && webhook?.secret)

  return (
    <section className="overflow-hidden rounded-2xl border border-neutral-200/80 bg-white">
      {/* Header + Supported Platform Logos */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-neutral-100 px-4 py-4 sm:px-6 sm:py-5">
        <div>
          <h2 className="text-[16px] font-semibold text-neutral-900">Monitoring Webhook</h2>
          <p className="mt-1 text-[14px] text-neutral-500">
            Paste the endpoint and signing secret (`X-Hub-Signature-256`) into your alerting platform.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {MONITORING_PLATFORMS.map((platform) => (
            <span
              key={platform.id}
              className="inline-flex items-center gap-2 rounded-full border border-neutral-200/80 bg-neutral-50/60 px-3 py-1.5 text-[13px] font-medium text-neutral-700"
            >
              <img
                src={platform.logo}
                alt={`${platform.name} logo`}
                className="size-4 object-contain"
                loading="lazy"
              />
              <span>{platform.name}</span>
            </span>
          ))}
        </div>
      </div>

      {/* Endpoint & Secret Rows */}
      <div className="divide-y divide-neutral-100">
        {/* Row 1: Webhook Endpoint URL */}
        <div className="flex flex-col items-start justify-between gap-3 px-4 py-4 sm:flex-row sm:items-center sm:gap-4 sm:px-6">
          <div className="min-w-44">
            <p className="text-[14.5px] font-medium text-neutral-900">Webhook Endpoint</p>
            <p className="mt-0.5 text-[13px] text-neutral-400">POST · application/json</p>
          </div>

          <div className="flex w-full flex-1 flex-wrap items-center justify-end gap-2.5 sm:w-auto">
            <code className="flex h-10 min-w-0 flex-1 items-center truncate rounded-xl border border-neutral-200/80 bg-neutral-50/70 px-3.5 font-mono text-[13px] text-neutral-800 select-all sm:max-w-md">
              {endpointUrl}
            </code>
            <Button
              variant="outline"
              size="sm"
              className="h-10 shrink-0 rounded-full bg-white px-4"
              onClick={() => copyText(endpointUrl, 'url')}
            >
              {copiedField === 'url' ? (
                <>
                  <Check className="size-3.5 text-emerald-600" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="size-3.5 text-neutral-500" />
                  Copy URL
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Row 2: Webhook Secret */}
        <div className="flex flex-col items-start justify-between gap-3 px-4 py-4 sm:flex-row sm:items-center sm:gap-4 sm:px-6">
          <div className="min-w-44">
            <div className="flex items-center gap-2">
              <p className="text-[14.5px] font-medium text-neutral-900">Webhook Secret</p>
              <span
                className={`size-2 rounded-full ${
                  isConfigured ? 'bg-emerald-500' : 'bg-neutral-300'
                }`}
              />
            </div>
            <p className="mt-0.5 text-[13px] text-neutral-400">
              HMAC-SHA256 · X-Hub-Signature-256
            </p>
          </div>

          <div className="flex w-full flex-1 flex-wrap items-center justify-start gap-2.5 sm:w-auto sm:justify-end">
            {isConfigured && webhook?.secret ? (
              <>
                <div className="flex h-10 min-w-[200px] flex-1 items-center justify-between rounded-xl border border-neutral-200/80 bg-neutral-50/70 px-3.5 font-mono text-[13px] text-neutral-800 sm:max-w-md">
                  <span className="truncate select-all">
                    {revealed ? webhook.secret : (webhook.preview ?? '••••••••••••')}
                  </span>
                  <button
                    type="button"
                    onClick={() => setRevealed((r) => !r)}
                    className="ml-2 shrink-0 cursor-pointer text-neutral-400 transition-colors duration-100 hover:text-neutral-800"
                    aria-label={revealed ? 'Hide secret' : 'Reveal secret'}
                    title={revealed ? 'Hide secret' : 'Reveal secret'}
                  >
                    {revealed ? (
                      <EyeOff className="size-4" />
                    ) : (
                      <Eye className="size-4" />
                    )}
                  </button>
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  className="h-10 rounded-full bg-white px-4"
                  onClick={() => copyText(webhook.secret!, 'secret')}
                >
                  {copiedField === 'secret' ? (
                    <>
                      <Check className="size-3.5 text-emerald-600" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="size-3.5 text-neutral-500" />
                      Copy secret
                    </>
                  )}
                </Button>
              </>
            ) : (
              <span className="rounded-full bg-neutral-100 px-3 py-1 text-[13px] text-neutral-500">
                No secret generated
              </span>
            )}

            <Button
              variant={isConfigured ? 'outline' : 'default'}
              size="sm"
              className={`h-10 rounded-full px-4 ${isConfigured ? 'bg-white' : ''}`}
              disabled={generateMutation.isPending}
              onClick={() => generateMutation.mutate()}
            >
              <RefreshCw
                className={`size-3.5 ${generateMutation.isPending ? 'animate-spin' : ''}`}
              />
              {generateMutation.isPending
                ? 'Generating…'
                : isConfigured
                  ? 'Regenerate secret'
                  : 'Generate secret'}
            </Button>
          </div>
        </div>
      </div>
    </section>
  )
}
