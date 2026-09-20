import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, ChevronDown } from 'lucide-react'
import { toast } from 'sonner'

import { llmSettingsApi, providerApi } from '../../../shared/lib/api'
import { queryKeys } from '../../../shared/lib/query-client'
import type {
  Provider,
  StepConfig,
  StepConfigUpdate,
  StepKeyInfo,
} from '../../../shared/types/settings'
import { Button, Input, Label } from '@/components/ui'
import { ProviderLogo } from './provider-logo'
import { ProviderSelect } from './provider-select'

const TIER_LABELS: Record<string, string> = {
  fast: 'fast',
  balanced: 'balanced',
  frontier: 'frontier',
}

const EMPTY_STEPS: StepConfig[] = []
const EMPTY_PROVIDERS: Provider[] = []
const EMPTY_STEP_KEYS: StepKeyInfo[] = []

interface StepDraft {
  provider_id: string
  model_id: string
  temperature: number | null
  max_output_tokens: number | null
  is_default: boolean
}

function toDraft(step: StepConfig): StepDraft {
  return {
    provider_id: step.provider_id,
    model_id: step.model_id,
    temperature: step.temperature,
    max_output_tokens: step.max_output_tokens,
    is_default: step.is_default,
  }
}

export function ModelStepsCard() {
  const queryClient = useQueryClient()

  const catalogQuery = useQuery({
    queryKey: queryKeys.settings.catalog(),
    queryFn: providerApi.catalog,
  })
  const stepsQuery = useQuery({
    queryKey: queryKeys.settings.llm(),
    queryFn: llmSettingsApi.get,
  })

  const [overrides, setOverrides] = useState<Record<string, Partial<StepDraft>>>({})
  const [showAdvanced, setShowAdvanced] = useState<Record<string, boolean>>({})

  const savedSteps = useMemo(
    () => stepsQuery.data?.steps ?? EMPTY_STEPS,
    [stepsQuery.data],
  )

  const configuredProviders = useMemo(
    () =>
      (catalogQuery.data?.providers ?? EMPTY_PROVIDERS).filter(
        (p) => p.credential_configured,
      ),
    [catalogQuery.data],
  )

  const steps = useMemo(
    () => catalogQuery.data?.steps ?? EMPTY_STEP_KEYS,
    [catalogQuery.data],
  )

  const providerById = useMemo(
    () =>
      Object.fromEntries(configuredProviders.map((p) => [p.id, p])) as Record<
        string,
        Provider
      >,
    [configuredProviders],
  )

  const drafts = useMemo(() => {
    const base: Record<string, StepDraft> = {}
    const fallbackProvider = configuredProviders[0]

    for (const step of savedSteps) {
      const merged = { ...toDraft(step), ...(overrides[step.step_key] ?? {}) }
      // Ensure the selected provider is one of the configured providers
      if (fallbackProvider && !providerById[merged.provider_id]) {
        merged.provider_id = fallbackProvider.id
        merged.model_id = fallbackProvider.models[0]?.id ?? ''
      }
      base[step.step_key] = merged
    }
    return base
  }, [savedSteps, overrides, configuredProviders, providerById])

  const dirty = savedSteps.some((s) => {
    const d = drafts[s.step_key]
    if (!d) return false
    return (
      d.provider_id !== s.provider_id ||
      d.model_id !== s.model_id ||
      d.temperature !== s.temperature ||
      d.max_output_tokens !== s.max_output_tokens
    )
  })

  const saveMutation = useMutation({
    mutationFn: (updates: StepConfigUpdate[]) => llmSettingsApi.save(updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.llm() })
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.catalog() })
      toast.success('Model configuration saved')
    },
    onError: (error) => {
      toast.error('Save failed', {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    },
  })

  const handleSave = () => {
    if (!stepsQuery.data) return
    const updates: StepConfigUpdate[] = stepsQuery.data.steps.map((s) => {
      const d = drafts[s.step_key] ?? toDraft(s)
      return {
        step_key: s.step_key,
        provider_id: d.provider_id,
        model_id: d.model_id,
        temperature: d.temperature,
        max_output_tokens: d.max_output_tokens,
      }
    })
    saveMutation.mutate(updates)
  }

  const update = (stepKey: string, patch: Partial<StepDraft>) => {
    setOverrides((prev) => ({ ...prev, [stepKey]: { ...prev[stepKey], ...patch } }))
  }

  if (catalogQuery.isLoading || stepsQuery.isLoading) {
    return (
      <div className="h-64 animate-pulse rounded-2xl border border-neutral-200/80 bg-white p-6" />
    )
  }

  if (configuredProviders.length === 0) {
    return (
      <section className="rounded-2xl border border-dashed border-neutral-200 bg-neutral-50/40 px-6 py-16 text-center">
        <p className="text-[16px] font-semibold text-neutral-900">
          No AI providers configured yet
        </p>
        <p className="mx-auto mt-1.5 max-w-md text-[14px] text-neutral-500">
          Add an API key for Google Gemini, OpenAI, Anthropic, or OpenRouter in Integrations to assign models to your pipeline steps.
        </p>
        <Link
          to="/integrations"
          className="mt-5 inline-flex items-center gap-2 rounded-full bg-neutral-900 px-5 py-2.5 text-[14px] font-medium text-white transition-colors hover:bg-neutral-800"
        >
          <span>Configure providers in Integrations</span>
          <ArrowRight className="size-4" />
        </Link>
      </section>
    )
  }

  return (
    <section className=" rounded-2xl border border-neutral-200/80 bg-white">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-neutral-100 px-6 py-5">
        <div>
          <h2 className="text-[16px] font-semibold text-neutral-900">
            Pipeline Model Routing
          </h2>
          <p className="mt-1 text-[14px] text-neutral-500">
            Showing models from your {configuredProviders.length} configured{' '}
            {configuredProviders.length === 1 ? 'provider' : 'providers'}.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="hidden items-center gap-1.5 sm:flex">
            {configuredProviders.map((p) => (
              <span
                key={p.id}
                className="inline-flex items-center gap-2 rounded-full border border-neutral-200/80 bg-neutral-50/70 px-3 py-1 text-[12.5px] font-medium text-neutral-700"
              >
                <ProviderLogo
                  providerId={p.id}
                  name={p.display_name}
                  className="size-4 border-0 bg-transparent shadow-none"
                  imgClassName="size-3.5"
                />
                <span>{p.display_name}</span>
              </span>
            ))}
          </div>

          <Button
            size="sm"
            className="rounded-full px-4"
            onClick={handleSave}
            disabled={!dirty || saveMutation.isPending}
          >
            {saveMutation.isPending ? 'Saving…' : dirty ? 'Save changes' : 'Saved'}
          </Button>
        </div>
      </div>

      <div className="divide-y divide-neutral-100">
        {savedSteps.map((step) => {
          const draft = drafts[step.step_key]
          if (!draft) return null
          const provider = providerById[draft.provider_id] ?? configuredProviders[0]
          const models = provider?.models ?? []
          const stepLabel =
            steps.find((s) => s.key === step.step_key)?.label ?? step.step_key

          return (
            <div
              key={step.step_key}
              className="px-4 py-4 transition-colors hover:bg-neutral-50/40 sm:px-6"
            >
              <div className="flex flex-col items-start justify-between gap-3.5 sm:flex-row sm:flex-wrap sm:items-center sm:gap-4">
                <div className="min-w-48">
                  <p className="text-[15px] font-medium text-neutral-900">{stepLabel}</p>
                  <p className="mt-0.5 text-[13px] text-neutral-400">{step.step_key}</p>
                </div>

                <div className="flex w-full flex-1 flex-wrap items-center justify-start gap-2.5 sm:w-auto sm:justify-end sm:gap-3">
                  <ProviderSelect
                    ariaLabel={`${stepLabel} provider`}
                    providers={configuredProviders}
                    value={provider.id}
                    onChange={(nextProviderId) => {
                      const next = providerById[nextProviderId]
                      update(step.step_key, {
                        provider_id: nextProviderId,
                        model_id: next?.models[0]?.id ?? '',
                      })
                    }}
                  />

                  <div className="relative flex w-full items-center sm:w-auto">
                    <select
                      aria-label={`${stepLabel} model`}
                      value={draft.model_id}
                      onChange={(e) => update(step.step_key, { model_id: e.target.value })}
                      className="h-10 w-full cursor-pointer appearance-none rounded-xl border border-neutral-200/90 bg-white pr-8 pl-3.5 text-[13.5px] font-medium text-neutral-800 transition-colors duration-100 hover:border-neutral-300 focus-visible:border-neutral-400 focus-visible:outline-none sm:min-w-56"
                    >
                      {models.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.label}
                          {TIER_LABELS[m.tier] ? ` (${TIER_LABELS[m.tier]})` : ''}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-2.5 size-4 text-neutral-400" />
                  </div>

                  <button
                    type="button"
                    onClick={() =>
                      setShowAdvanced((prev) => ({
                        ...prev,
                        [step.step_key]: !prev[step.step_key],
                      }))
                    }
                    className="cursor-pointer text-[13px] font-medium text-neutral-400 transition-colors hover:text-neutral-800"
                  >
                    {showAdvanced[step.step_key] ? 'Hide params' : 'Params'}
                  </button>
                </div>
              </div>

              {showAdvanced[step.step_key] && (
                <div className="mt-4 flex flex-wrap items-end gap-3 border-t border-neutral-100 pt-4">
                  <div className="w-32 space-y-1.5">
                    <Label className="text-[13px] text-neutral-600">
                      Temperature
                    </Label>
                    <Input
                      type="number"
                      step="0.1"
                      min={0}
                      max={2}
                      value={draft.temperature ?? ''}
                      placeholder="Default"
                      onChange={(e) =>
                        update(step.step_key, {
                          temperature:
                            e.target.value === '' ? null : Number(e.target.value),
                        })
                      }
                      className="h-9 rounded-xl bg-white text-[13px]"
                    />
                  </div>
                  <div className="w-40 space-y-1.5">
                    <Label className="text-[13px] text-neutral-600">
                      Max tokens
                    </Label>
                    <Input
                      type="number"
                      min={1}
                      value={draft.max_output_tokens ?? ''}
                      placeholder="Default"
                      onChange={(e) =>
                        update(step.step_key, {
                          max_output_tokens:
                            e.target.value === '' ? null : Number(e.target.value),
                        })
                      }
                      className="h-9 rounded-xl bg-white text-[13px]"
                    />
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="rounded-full"
                    onClick={() =>
                      update(step.step_key, { temperature: null, max_output_tokens: null })
                    }
                  >
                    Reset
                  </Button>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
