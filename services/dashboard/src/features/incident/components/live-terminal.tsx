import { useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'
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
  fetch_logs: 'Cluster Diagnostics (kubectl)',
  context_gathering: 'Context Gathering & Diagnostics',
  gather_context: 'Context Gathering & Diagnostics',
  refer_runbooks: 'Runbook Retrieval',
  recommended_steps: 'Remediation Synthesis',
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
      <span className="inline-flex items-center rounded-full bg-red-50 px-2.5 py-0.5 text-[12px] font-medium text-red-700 ring-1 ring-red-200/70">
        P1 Critical
      </span>
    )
  }
  if (s === 'P2') {
    return (
      <span className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-[12px] font-medium text-amber-800 ring-1 ring-amber-200/70">
        P2 High
      </span>
    )
  }
  return (
    <span className="inline-flex items-center rounded-full bg-neutral-100 px-2.5 py-0.5 text-[12px] font-medium text-neutral-700">
      {s}
    </span>
  )
}

export function LiveTerminal({ steps, live = false }: { steps: LiveStep[]; live?: boolean }) {
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({})

  const toggleExpand = (id: string) => {
    setExpandedSteps((prev) => ({
      ...prev,
      [id]: prev[id] === undefined ? false : !prev[id],
    }))
  }

  const isExpanded = (id: string) => expandedSteps[id] ?? true

  if (steps.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-neutral-200/80 bg-white px-6 py-20">
        <div className="size-5 animate-spin rounded-full border-2 border-neutral-200 border-t-neutral-900" />
        <p className="text-[15px] text-neutral-500">
          Waiting for initial agent step…
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {steps.map((step, index) => {
        const data = (step.output_data ?? {}) as Record<string, any>
        const open = isExpanded(step.id)
        const severity = data.severity

        return (
          <div
            key={step.id}
            className="animate-step-in overflow-hidden rounded-2xl border border-neutral-200/80 bg-white"
            style={{
              contentVisibility: 'auto',
              containIntrinsicSize: 'auto 240px',
              contain: 'content',
              transform: 'translateZ(0)',
            }}
          >
            <button
              type="button"
              onClick={() => toggleExpand(step.id)}
              className="flex w-full cursor-pointer items-center justify-between gap-3 px-4 py-3.5 text-left transition-colors select-none hover:bg-neutral-50/70 sm:px-6 sm:py-4"
            >
              <div className="flex items-center gap-3.5">
                <span
                  className={`flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-medium ${
                    step.status === 'COMPLETED'
                      ? 'bg-neutral-900 text-white'
                      : step.status === 'FAILED'
                        ? 'bg-red-100 text-red-700'
                        : 'bg-amber-100 text-amber-800 animate-pulse'
                  }`}
                >
                  {step.status === 'COMPLETED' ? (
                    <Check className="size-3.5" strokeWidth={2.5} />
                  ) : (
                    index + 1
                  )}
                </span>

                <div className="flex flex-wrap items-center gap-2.5">
                  <span className="text-[15.5px] font-semibold text-neutral-900">
                    {label(step.name)}
                  </span>
                  <SeverityBadge severity={severity} />
                </div>
              </div>

              <div className="flex items-center gap-3">
                <span
                  className={`text-[13px] font-medium ${
                    step.status === 'COMPLETED'
                      ? 'text-neutral-400'
                      : step.status === 'FAILED'
                        ? 'text-red-600'
                        : 'text-amber-700'
                  }`}
                >
                  {VERB[step.status]}
                </span>
                <ChevronDown
                  className={`size-4 text-neutral-400 transition-transform duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] ${
                    open ? 'rotate-180' : ''
                  }`}
                />
              </div>
            </button>

            <div
              className={`grid transition-[grid-template-rows,opacity] duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] ${
                open ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
              }`}
            >
              <div className="overflow-hidden">
                <div className="border-t border-neutral-100 px-4 pt-4 pb-5 sm:px-6 sm:pb-6">
                  {step.status === 'RUNNING' && !step.output_data && (
                    <div className="flex items-center gap-3 rounded-xl border border-amber-200/80 bg-amber-50/50 px-4 py-3 text-[14px] text-amber-900">
                      <span className="size-2 animate-ping rounded-full bg-amber-500" />
                      <span>Agent is running this step and gathering cluster signals…</span>
                    </div>
                  )}

                  {step.error_message && (
                    <div className="rounded-xl border border-red-200/80 bg-red-50/60 p-4 text-[14px] text-red-800">
                      <p className="font-medium text-red-900">Step Failed</p>
                      <p className="mt-1 font-mono text-[13px]">{step.error_message}</p>
                    </div>
                  )}

                  <StepOutput step={step} />

                  {step.status !== 'RUNNING' && Object.keys(data).length > 0 && (
                    <details className="mt-4 group">
                      <summary className="inline-flex cursor-pointer select-none items-center gap-1.5 text-[13px] font-medium text-neutral-400 transition-colors hover:text-neutral-700">
                        <span>View raw step output</span>
                      </summary>
                      <pre
                        className="mt-2.5 max-h-64 overflow-auto rounded-2xl bg-[#141414] p-4 font-mono text-[12.5px] leading-relaxed text-neutral-200"
                        style={{ willChange: 'transform' }}
                      >
                        {JSON.stringify(data, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            </div>
          </div>
        )
      })}

      {live && (
        <div className="animate-step-in flex items-center gap-3.5 rounded-2xl border border-neutral-200/80 bg-neutral-50/60 px-6 py-4">
          <span className="relative flex size-2.5">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-amber-400 opacity-75" />
            <span className="relative inline-flex size-2.5 rounded-full bg-amber-500" />
          </span>
          <span className="text-[14.5px] font-medium text-neutral-700">
            Running next pipeline step…
          </span>
        </div>
      )}
    </div>
  )
}
