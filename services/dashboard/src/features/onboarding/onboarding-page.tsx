import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Check } from 'lucide-react'

import { BrandLogo } from '../../shared/components/brand-logo'
import { RunbookUploader } from '../runbooks/components/runbook-uploader'
import { useRunbooksList } from '../runbooks/hooks/use-runbooks'
import { IntegrationsCard } from '../settings/components/integrations-card'
import { KubernetesClusterCard } from '../settings/components/kubernetes-cluster-card'
import { ModelStepsCard } from '../settings/components/model-steps-card'
import { MonitoringSourcesCard } from '../settings/components/monitoring-sources-card'

const ONBOARDING_STEPS = [
  {
    key: 'webhook',
    title: 'Alert Webhook & Secret',
    subtitle: 'Generate your webhook secret and copy the endpoint URL for your monitoring platform.',
  },
  {
    key: 'providers',
    title: 'AI Model Providers',
    subtitle: 'Configure at least one LLM provider API key so the agent can triage incidents.',
  },
  {
    key: 'routing',
    title: 'Pipeline Model Routing',
    subtitle: 'Choose which configured provider and model runs each stage of the pipeline.',
  },
  {
    key: 'runbooks',
    title: 'Upload Runbooks',
    subtitle: 'Upload Markdown operational playbooks so the agent can reference your recovery procedures.',
  },
  {
    key: 'kubernetes',
    title: 'Kubernetes Cluster',
    subtitle: 'Connect your production cluster via ServiceAccount token, or continue in Mock Cluster Mode.',
  },
] as const

export function OnboardingPage() {
  const navigate = useNavigate()
  const [stepIndex, setStepIndex] = useState(0)
  const { data: runbooks, refetch: refetchRunbooks } = useRunbooksList()

  const currentStep = ONBOARDING_STEPS[stepIndex]
  const isFirst = stepIndex === 0
  const isLast = stepIndex === ONBOARDING_STEPS.length - 1

  const handleNext = () => {
    if (isLast) {
      navigate('/dashboard', { replace: true })
    } else {
      setStepIndex((i) => i + 1)
    }
  }

  const handleBack = () => {
    if (!isFirst) {
      setStepIndex((i) => i - 1)
    }
  }

  return (
    <div className="min-h-screen bg-[#FAFAFA] text-foreground antialiased selection:bg-neutral-900 selection:text-white">
      {/* Top Bar */}
      <header className="sticky top-0 z-30 border-b border-neutral-200/70 bg-white/90 backdrop-blur-md">
        <div className="mx-auto flex h-15 max-w-5xl items-center justify-between px-6">
          <BrandLogo />

          <button
            type="button"
            onClick={() => navigate('/dashboard', { replace: true })}
            className="cursor-pointer text-[13.5px] font-medium text-neutral-500 transition-colors hover:text-neutral-900"
          >
            Skip to dashboard →
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6 sm:py-10">
        {/* Stepper Pills */}
        <nav aria-label="Onboarding progress" className="mb-8 flex flex-wrap items-center gap-2">
          {ONBOARDING_STEPS.map((s, idx) => {
            const active = idx === stepIndex
            const completed = idx < stepIndex
            return (
              <button
                key={s.key}
                type="button"
                onClick={() => setStepIndex(idx)}
                className={`inline-flex cursor-pointer items-center gap-2 rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors ${active
                    ? 'bg-neutral-900 text-white'
                    : completed
                      ? 'bg-neutral-200/80 text-neutral-800 hover:bg-neutral-200'
                      : 'bg-white text-neutral-500 ring-1 ring-neutral-200/80 hover:text-neutral-800'
                  }`}
              >
                <span
                  className={`flex size-4.5 items-center justify-center rounded-full text-[11px] tabular-nums ${active
                      ? 'bg-white/20 text-white'
                      : completed
                        ? 'bg-neutral-900 text-white'
                        : 'bg-neutral-100 text-neutral-500'
                    }`}
                >
                  {completed ? <Check className="size-3" strokeWidth={2.5} /> : idx + 1}
                </span>
                <span>{s.title}</span>
              </button>
            )
          })}
        </nav>

        {/* Active Step Header */}
        <div className="mb-6">
          <p className="text-[13px] font-medium text-neutral-400">
            Step {stepIndex + 1} of {ONBOARDING_STEPS.length}
          </p>
          <h1 className="mt-1 text-[24px] font-semibold tracking-tight text-neutral-900">
            {currentStep.title}
          </h1>
          <p className="mt-1 text-[15px] text-neutral-500">{currentStep.subtitle}</p>
        </div>

        {/* Step Content */}
        <div className="min-h-[320px]">
          {stepIndex === 0 && <MonitoringSourcesCard />}
          {stepIndex === 1 && <IntegrationsCard />}
          {stepIndex === 2 && <ModelStepsCard />}
          {stepIndex === 3 && (
            <div className="flex flex-col gap-5">
              {runbooks && runbooks.length > 0 && (
                <div className="flex items-center justify-between rounded-2xl border border-emerald-200/80 bg-emerald-50/60 px-5 py-3.5 text-[14px] text-emerald-900">
                  <span>
                    <strong>{runbooks.length}</strong>{' '}
                    {runbooks.length === 1 ? 'runbook' : 'runbooks'} uploaded ({runbooks.map((r) => r.title).join(', ')}).
                  </span>
                </div>
              )}
              <RunbookUploader onUploaded={() => refetchRunbooks()} />
            </div>
          )}
          {stepIndex === 4 && <KubernetesClusterCard />}
        </div>

        {/* Bottom Navigation Bar */}
        <footer className="mt-8 flex items-center justify-between border-t border-neutral-200/80 pt-6">
          <button
            type="button"
            onClick={handleBack}
            disabled={isFirst}
            className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-neutral-200 bg-white px-4 py-2 text-[14px] font-medium text-neutral-700 transition-colors hover:bg-neutral-50 disabled:pointer-events-none disabled:opacity-40"
          >
            <ArrowLeft className="size-4" />
            <span>Back</span>
          </button>

          <button
            type="button"
            onClick={handleNext}
            className="inline-flex cursor-pointer items-center gap-2 rounded-full bg-neutral-900 px-5 py-2.5 text-[14px] font-medium text-white transition-colors hover:bg-neutral-800"
          >
            <span>{isLast ? 'Finish setup' : 'Continue'}</span>
            <ArrowRight className="size-4" />
          </button>
        </footer>
      </main>
    </div>
  )
}
