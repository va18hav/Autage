import { useEffect, useState } from 'react'
import type { IncidentStep } from '../../../shared/types/incident'
import { TimeAgo } from '../../../shared/components/time-ago'
import { StepOutput } from '../../incident/components/step-output'
import type { LiveStep } from '../../incident/store/incident-live-store'

export function StepTimeline({ steps }: { steps: IncidentStep[] }) {
  // Two-phase mount: paint the timeline skeleton immediately when the drawer
  // opens, then bring in the heavy terminal payloads off the critical path
  // (after first paint, in an idle slice). Keeps the open interaction jank-free.
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
    return <p className="text-sm text-neutral-400">No steps recorded yet.</p>
  }

  return (
    <ol className="space-y-0">
      {steps.map((step, index) => (
        <li
          key={step.id}
          className="relative flex gap-4 pb-6 last:pb-0"
          // Skip layout/paint for offscreen steps and give each card its own
          // GPU layer — scrolling composites pre-rasterized layers instead of
          // re-rasterizing text on the CPU thread.
          style={{
            contentVisibility: 'auto',
            containIntrinsicSize: 'auto 240px',
            contain: 'content',
            transform: 'translateZ(0)',
          }}
        >
          {index < steps.length - 1 && (
            <span className="absolute left-[7px] top-4 h-full w-px bg-neutral-200" aria-hidden />
          )}
          <span
            className={`relative mt-1.5 size-[15px] shrink-0 rounded-full border-2 bg-white ${
              step.status === 'COMPLETED'
                ? 'border-emerald-500'
                : step.status === 'FAILED'
                  ? 'border-red-500'
                  : 'border-amber-400'
            }`}
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline justify-between gap-3">
              <p className="text-sm font-medium text-neutral-900">
                {formatStepName(step.step_name)}
              </p>
              <span className="shrink-0 text-xs text-neutral-400">
                <TimeAgo date={step.created_at} />
              </span>
            </div>
            {step.error_message && (
              <p className="mt-1 text-xs text-red-600">{step.error_message}</p>
            )}
            {step.output_data && Object.keys(step.output_data).length > 0 && heavyReady && (
              <div className="mt-2">
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
  return name
    .split('_')
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(' ')
}
