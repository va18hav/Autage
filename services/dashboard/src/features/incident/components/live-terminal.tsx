import { useState } from 'react'
import type { StepStatus } from '../../../shared/types/incident'
import type { LiveStep } from '../store/incident-live-store'
import { StepOutput } from './step-output'

const VERB: Record<StepStatus, string> = {
  RUNNING: 'Running',
  COMPLETED: 'Completed',
  FAILED: 'Failed',
}

const LABELS: Record<string, string> = {
  triage: 'Triage & Classification',
  process_alert: 'Triage & Classification',
  route_p1: 'Route P1 Critical',
  route_p2: 'Route P2 Standard',
  route_p3: 'Route P3 Low Severity',
  context_gathering: 'Context Gathering & Diagnostics',
  gather_context: 'Context Gathering & Diagnostics',
}

function label(name: string) {
  return (
    LABELS[name] ??
    name
      .split('_')
      .map((w) => w[0].toUpperCase() + w.slice(1))
      .join(' ')
  )
}

function SeverityBadge({ severity }: { severity?: string }) {
  if (!severity) return null
  const s = severity.toUpperCase()
  if (s === 'P1') {
    return (
      <span className="inline-flex items-center rounded-md border border-red-200 bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-700">
        P1 Critical
      </span>
    )
  }
  if (s === 'P2') {
    return (
      <span className="inline-flex items-center rounded-md border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700">
        P2 High
      </span>
    )
  }
  return (
    <span className="inline-flex items-center rounded-md border border-blue-200 bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-700">
      {s}
    </span>
  )
}

export function LiveTerminal({ steps }: { steps: LiveStep[] }) {
  // Keep track of which steps are expanded (default: all expanded)
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({})

  const toggleExpand = (id: string) => {
    setExpandedSteps((prev) => ({
      ...prev,
      // Default open if undefined, toggle to false
      [id]: prev[id] === undefined ? false : !prev[id],
    }))
  }

  const isExpanded = (id: string) => {
    // Open by default
    return expandedSteps[id] ?? true
  }

  return (
    <div className="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-xs">
      <div className="flex items-center justify-between border-b border-neutral-100 bg-neutral-50/60 px-5 py-3.5">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-neutral-800">Agent Activity Timeline</h2>
          <span className="rounded-full bg-neutral-200/80 px-2 py-0.5 text-xs font-medium text-neutral-600">
            {steps.length} {steps.length === 1 ? 'step' : 'steps'}
          </span>
        </div>
      </div>

      {steps.length === 0 ? (
        <div className="flex flex-col items-center gap-3 px-5 py-16">
          <div className="size-6 animate-spin rounded-full border-2 border-neutral-200 border-t-neutral-600" />
          <p className="text-sm text-neutral-500">Waiting for agent activity…</p>
        </div>
      ) : (
        <ul className="divide-y divide-neutral-100">
          {steps.map((step) => {
            const data = (step.output_data ?? {}) as Record<string, any>
            const open = isExpanded(step.id)
            const severity = data.severity

            return (
              <li
                key={step.id}
                className="transition-colors hover:bg-neutral-50/30"
                style={{
                  contentVisibility: 'auto',
                  containIntrinsicSize: 'auto 240px',
                  contain: 'content',
                  transform: 'translateZ(0)',
                }}
              >
                {/* Header Row */}
                <button
                  type="button"
                  onClick={() => toggleExpand(step.id)}
                  className="flex w-full items-center justify-between px-5 py-4 text-left transition-colors cursor-pointer select-none"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`size-2.5 rounded-full ring-4 ${
                        step.status === 'COMPLETED'
                          ? 'bg-emerald-500 ring-emerald-50'
                          : step.status === 'FAILED'
                            ? 'bg-red-500 ring-red-50'
                            : 'bg-amber-500 ring-amber-50 animate-pulse'
                      }`}
                    />
                    <div className="flex items-center gap-2.5">
                      <span className="text-sm font-medium text-neutral-900">
                        {label(step.name)}
                      </span>
                      <SeverityBadge severity={severity} />
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <span
                      className={`text-xs font-medium ${
                        step.status === 'COMPLETED'
                          ? 'text-emerald-700'
                          : step.status === 'FAILED'
                            ? 'text-red-700'
                            : 'text-amber-700'
                      }`}
                    >
                      {VERB[step.status]}
                    </span>
                    <svg
                      className={`size-4 text-neutral-400 transition-transform duration-200 ${
                        open ? 'rotate-180' : ''
                      }`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </button>

                {/* Expanded Details Body */}
                {open && (
                  <div className="border-t border-neutral-100/80 bg-neutral-50/40 px-5 pt-3 pb-5">
                    {step.status === 'RUNNING' && !step.output_data && (
                      <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50/80 border border-amber-200/60 rounded-lg p-3">
                        <span className="size-2 rounded-full bg-amber-500 animate-ping" />
                        Agent is actively running this step and gathering cluster signals...
                      </div>
                    )}

                    {step.error_message && (
                      <div className="rounded-lg border border-red-200 bg-red-50 p-3.5 text-xs text-red-800">
                        <p className="font-semibold">Step Failed</p>
                        <p className="mt-1 font-mono">{step.error_message}</p>
                      </div>
                    )}

                    {/* Step specific renderings */}
                    <StepOutput step={step} />

                    {/* Full node output once the step has finished */}
                    {step.status !== 'RUNNING' && Object.keys(data).length > 0 && (
                      <details className="mt-3">
                        <summary className="cursor-pointer select-none text-xs font-semibold uppercase tracking-wider text-neutral-400 transition-colors hover:text-neutral-600">
                          Raw Node Output
                        </summary>
                        <pre
                          className="mt-2 max-h-60 overflow-auto rounded-lg bg-neutral-900 p-3 font-mono text-[11px] leading-relaxed text-neutral-200"
                          style={{ willChange: 'transform' }}
                        >
                          {JSON.stringify(data, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
