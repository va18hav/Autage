import { useEffect, useState } from 'react'
import { Check } from 'lucide-react'
import type { IncidentStep } from '../../../shared/types/incident'
import { TimeAgo } from '../../../shared/components/time-ago'
import { StepOutput } from '../../incident/components/step-output'
import type { LiveStep } from '../../incident/store/incident-live-store'

const STEP_LABELS: Record<string, string> = {
  triage: 'Triage & Classification',
  process_alert: 'Triage & Classification',
  route_p1: 'Route P1 Critical',
  route_p2: 'Route P2 Standard',
  route_p3: 'Route P3 Low Severity',
  fetch_logs: 'Cluster Diagnostics (kubectl)',
  context_gathering: 'Context Gathering & Diagnostics',
  gather_context: 'Context Gathering & Diagnostics',
  refer_runbooks: 'Runbook Retrieval',
  recommended_steps: 'Remediation Synthesis',
}

export function StepTimeline({ steps }: { steps: IncidentStep[] }) {
  const [heavyReady, setHeavyReady] = useState(false)

  useEffect(() => {
    let idle: number | undefined
    const raf = requestAnimationFrame(() => {
      idle = requestIdleCallback(
        () => setHeavyReady(true),
        { timeout: 300 },
      )
    })
    return () => {
      cancelAnimationFrame(raf)
      if (idle !== undefined) cancelIdleCallback(idle)
    }
  }, [])

  if (!steps.length) {
    return (
      <div className="rounded-2xl border border-dashed border-neutral-200 bg-neutral-50/50 px-6 py-10 text-center">
        <p className="text-[14px] text-neutral-400">No execution steps recorded yet.</p>
      </div>
    )
  }

  return (
    <ol className="space-y-0">
      {steps.map((step, index) => (
        <li
          key={step.id}
          className="relative flex gap-4 pb-8 last:pb-0"
          style={{
            contentVisibility: 'auto',
            containIntrinsicSize: 'auto 240px',
            contain: 'content',
            transform: 'translateZ(0)',
          }}
        >
          {index < steps.length - 1 && (
            <span
              className="absolute left-[13px] top-8 h-[calc(100%-16px)] w-px bg-neutral-200"
              aria-hidden
            />
          )}
          <span
            className={`relative mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-medium ${
              step.status === 'COMPLETED'
                ? 'bg-neutral-900 text-white'
                : step.status === 'FAILED'
                  ? 'bg-red-100 text-red-700'
                  : 'bg-amber-100 text-amber-800'
            }`}
          >
            {step.status === 'COMPLETED' ? (
              <Check className="size-3.5" strokeWidth={2.5} />
            ) : (
              index + 1
            )}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-[15px] font-medium text-neutral-900">
                {formatStepName(step.step_name)}
              </p>
              <span className="shrink-0 text-[13px] text-neutral-400">
                <TimeAgo date={step.created_at} />
              </span>
            </div>
            {step.error_message && (
              <div className="mt-3 rounded-xl border border-red-200/80 bg-red-50/70 px-4 py-3 text-[13.5px] text-red-700">
                {step.error_message}
              </div>
            )}
            {step.output_data && Object.keys(step.output_data).length > 0 && heavyReady && (
              <div className="mt-3">
                <StepOutput step={toLiveStep(step)} />
              </div>
            )}
          </div>
        </li>
      ))}
    </ol>
  )
}

function toLiveStep(step: IncidentStep): LiveStep {
  return {
    id: step.id,
    name: step.step_name,
    status: step.status,
    output_data: step.output_data,
    input_data: step.input_data,
    error_message: step.error_message,
  }
}

function formatStepName(name: string) {
  if (STEP_LABELS[name]) return STEP_LABELS[name]
  return name
    .split('_')
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(' ')
}
