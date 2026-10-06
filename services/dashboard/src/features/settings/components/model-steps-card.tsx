import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { llmSettingsApi, providerApi } from '../../../shared/lib/api'
import { queryKeys } from '../../../shared/lib/query-client'
import type {
  Provider,
  StepConfig,
  StepConfigUpdate,
  StepKeyInfo,
} from '../../../shared/types/settings'
import { Badge } from '@/components/ui'
import { Button } from '@/components/ui'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui'
import { Input } from '@/components/ui'
import { Label } from '@/components/ui'

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

  // Server truth + per-step local overrides only — no state copying of the
  // whole dataset, so refetches stay consistent and dirty checks stay simple.
  const [overrides, setOverrides] = useState<Record<string, Partial<StepDraft>>>({})
  const [showAdvanced, setShowAdvanced] = useState<Record<string, boolean>>({})

  const savedSteps = useMemo(
    () => stepsQuery.data?.steps ?? EMPTY_STEPS,
    [stepsQuery.data],
  )
  const drafts = useMemo(() => {
    const base: Record<string, StepDraft> = {}
    for (const step of savedSteps) {
      base[step.step_key] = { ...toDraft(step), ...(overrides[step.step_key] ?? {}) }
    }
    return base
  }, [savedSteps, overrides])

  const providers = useMemo(
    () => catalogQuery.data?.providers ?? EMPTY_PROVIDERS,
    [catalogQuery.data],
  )
  const steps = useMemo(
    () => catalogQuery.data?.steps ?? EMPTY_STEP_KEYS,
    [catalogQuery.data],
  )
  const providerById = useMemo(
    () => Object.fromEntries(providers.map((p) => [p.id, p])) as Record<string, Provider>,
    [providers],
  )

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
    return <Card className="animate-pulse bg-neutral-200/40" />
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Model by step</CardTitle>
        <p className="text-sm text-muted-foreground">
          Choose which provider and model handles each step of the pipeline — e.g. a
          light, fast model for triage and a stronger one for recommendations.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {savedSteps.map((step) => {
          const draft = drafts[step.step_key]
          if (!draft) return null
          const provider = providerById[draft.provider_id]
          const models = provider?.models ?? []
          const missingCredential =
            provider && !provider.credential_configured && provider.id !== 'ollama'
          const stepLabel = steps.find((s) => s.key === step.step_key)?.label ?? step.step_key

          return (
            <div
              key={step.step_key}
              className="rounded-lg border bg-neutral-50/60 px-3.5 py-3"
            >
              <div className="flex flex-wrap items-center gap-3">
                <div className="min-w-44 flex-1">
                  <Label className="text-xs text-muted-foreground">{stepLabel}</Label>
                  <select
                    value={draft.provider_id}
                    onChange={(e) => {
                      const next = providerById[e.target.value]
                      update(step.step_key, {
                        provider_id: e.target.value,
                        model_id: next?.models[0]?.id ?? '',
                      })
                    }}
                    className="mt-1 flex h-9 w-full appearance-none rounded-md border border-input bg-white px-3 py-1 text-sm shadow-xs focus-visible:border-neutral-400 focus-visible:outline-none"
                  >
                    {providers.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.display_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="min-w-52 flex-1">
                  <Label className="text-xs text-muted-foreground">Model</Label>
                  <select
                    value={draft.model_id}
                    onChange={(e) => update(step.step_key, { model_id: e.target.value })}
                    className="mt-1 flex h-9 w-full appearance-none rounded-md border border-input bg-white px-3 py-1 text-sm shadow-xs focus-visible:border-neutral-400 focus-visible:outline-none"
                  >
                    {models.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label}
                        {TIER_LABELS[m.tier] ? ` — ${TIER_LABELS[m.tier]}` : ''}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex items-end gap-2 pt-4">
                  <Badge
                    variant="outline"
                    className={
                      missingCredential
                        ? 'border-amber-300 bg-amber-50 text-amber-700'
                        : draft.is_default
                          ? 'text-muted-foreground'
                          : ''
                    }
                  >
                    {missingCredential
                      ? 'key needed'
                      : draft.is_default
                        ? 'default'
                        : 'custom'}
                  </Badge>
                  <button
                    type="button"
                    onClick={() =>
                      setShowAdvanced((prev) => ({
                        ...prev,
                        [step.step_key]: !prev[step.step_key],
                      }))
                    }
                    className="text-xs text-muted-foreground underline-offset-2 hover:underline"
                  >
                    advanced
                  </button>
                </div>
              </div>

              {showAdvanced[step.step_key] && (
                <div className="mt-3 flex flex-wrap items-end gap-3 border-t pt-3">
                  <div className="w-28 space-y-1">
                    <Label className="text-xs text-muted-foreground">
                      Temperature
                    </Label>
                    <Input
                      type="number"
                      step="0.1"
                      min={0}
                      max={2}
                      value={draft.temperature ?? ''}
                      placeholder="provider default"
                      onChange={(e) =>
                        update(step.step_key, {
                          temperature:
                            e.target.value === '' ? null : Number(e.target.value),
                        })
                      }
                      className="h-9 bg-white"
                    />
                  </div>
                  <div className="w-40 space-y-1">
                    <Label className="text-xs text-muted-foreground">
                      Max output tokens
                    </Label>
                    <Input
                      type="number"
                      min={1}
                      value={draft.max_output_tokens ?? ''}
                      placeholder="provider default"
                      onChange={(e) =>
                        update(step.step_key, {
                          max_output_tokens:
                            e.target.value === '' ? null : Number(e.target.value),
                        })
                      }
                      className="h-9 bg-white"
                    />
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-9"
                    onClick={() => update(step.step_key, { temperature: null, max_output_tokens: null })}
                  >
                    Clear overrides
                  </Button>
                </div>
              )}

              {missingCredential && (
                <p className="mt-2 text-xs text-amber-700">
                  {provider.display_name} needs an API key — add it under Integrations
                  below before incidents can run on this model.
                </p>
              )}
            </div>
          )
        })}

        <div className="flex justify-end pt-1">
          <Button onClick={handleSave} disabled={!dirty || saveMutation.isPending}>
            {saveMutation.isPending ? 'Saving…' : dirty ? 'Save changes' : 'Saved'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
