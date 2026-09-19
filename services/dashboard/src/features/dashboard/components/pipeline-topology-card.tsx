import type { ComponentType, SVGProps } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import {
  StageDiagnosticsIcon,
  StageRecommendationsIcon,
  StageRunbooksIcon,
  StageTriageIcon,
} from '../../../shared/components/icons'
import type { Provider, StepConfig, StepKeyInfo } from '../../../shared/types/settings'
import { ProviderLogo } from '../../settings/components/provider-logo'

const STAGE_ICONS: Record<string, ComponentType<SVGProps<SVGSVGElement>>> = {
  triage: StageTriageIcon,
  diagnostics: StageDiagnosticsIcon,
  runbooks: StageRunbooksIcon,
  recommendations: StageRecommendationsIcon,
}

const STAGE_TITLES: Record<string, string> = {
  triage: 'Alert Triage',
  diagnostics: 'Cluster Diagnostics',
  runbooks: 'Runbook Reasoning',
  recommendations: 'Remediation Plan',
}

interface PipelineTopologyCardProps {
  steps: StepConfig[]
  stepKeys: StepKeyInfo[]
  providers: Provider[]
}

export function PipelineTopologyCard({
  steps,
  stepKeys,
  providers,
}: PipelineTopologyCardProps) {
  if (steps.length === 0) return null

  const providerMap = Object.fromEntries(providers.map((p) => [p.id, p]))
  const labelMap = Object.fromEntries(stepKeys.map((k) => [k.key, k.label]))

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-[17px] font-semibold tracking-tight text-neutral-900">
            Agent Pipeline Topology
          </h2>
          <p className="text-[14px] text-neutral-500">
            Active model routing across each stage of autonomous incident triage.
          </p>
        </div>

        <Link
          to="/settings"
          className="inline-flex items-center gap-1.5 text-[14px] font-medium text-neutral-600 transition-colors hover:text-neutral-950"
        >
          <span>Configure routing</span>
          <ArrowRight className="size-4" />
        </Link>
      </div>

      <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        {steps.map((step, index) => {
          const provider = providerMap[step.provider_id]
          const model = provider?.models.find((m) => m.id === step.model_id)
          const label =
            STAGE_TITLES[step.step_key] ?? labelMap[step.step_key] ?? step.step_key
          const StageIcon = STAGE_ICONS[step.step_key] ?? StageTriageIcon

          return (
            <div
              key={step.step_key}
              className="relative flex flex-col justify-between rounded-2xl border border-neutral-200/80 bg-white p-5"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="flex size-9 items-center justify-center rounded-xl border border-neutral-200/80 bg-neutral-50/70 text-neutral-800">
                    <StageIcon className="size-[18px]" />
                  </span>
                  <span className="font-mono text-[11.5px] text-neutral-400">
                    0{index + 1} · {step.step_key}
                  </span>
                </div>
                <p className="mt-3.5 text-[15px] font-semibold text-neutral-900">
                  {label}
                </p>
              </div>

              <div className="mt-5 flex items-center gap-2.5 border-t border-neutral-100 pt-3.5">
                <ProviderLogo
                  providerId={step.provider_id}
                  name={provider?.display_name}
                  className="size-6 rounded-md border-0 bg-neutral-100/80 shadow-none"
                  imgClassName="size-4"
                />
                <div className="min-w-0">
                  <p className="truncate text-[13.5px] font-medium text-neutral-800">
                    {model?.label ?? step.model_id}
                  </p>
                  <p className="truncate text-[12px] text-neutral-400">
                    {provider?.display_name ?? step.provider_id}
                  </p>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
