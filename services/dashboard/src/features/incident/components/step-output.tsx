import { memo } from 'react'
import type { LiveStep } from '../store/incident-live-store'

/**
 * Rich renderer for a single node's output — shared by the live terminal and
 * the dashboard drawer timeline so both views display step data identically.
 * Memoized: incident refetches re-render parents without reworking every step.
 */
export const StepOutput = memo(function StepOutput({ step }: { step: LiveStep }) {
  const data = (step.output_data ?? {}) as Record<string, any>
  const isTriage = step.name === 'triage' || step.name === 'process_alert'
  const isContext = step.name === 'context_gathering' || step.name === 'gather_context'
  const isRoute = step.name.startsWith('route_')

  if (isTriage && (data.summary || data.description)) {
    return (
      <div className="space-y-3">
        {data.summary && (
          <div className="rounded-lg border border-neutral-200/80 bg-white p-3.5 text-sm text-neutral-700 shadow-2xs">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-neutral-400 mb-1.5">
              Triage Summary
            </h4>
            <p className="leading-relaxed text-neutral-800">{data.summary}</p>
          </div>
        )}

        {data.description && data.description !== data.summary && (
          <div className="text-xs text-neutral-600 bg-white p-3 rounded-lg border border-neutral-200/70">
            <span className="font-medium text-neutral-700">Details: </span>
            {data.description}
          </div>
        )}
      </div>
    )
  }

  if (isContext) {
    const summary = data.context_summary ?? {}
    const context = data.context ?? {}
    const toolsExecuted = Object.keys(context)

    return (
      <div className="space-y-3">
        {summary.root_cause_hypothesis && (
          <div className="rounded-lg border border-amber-200/70 bg-amber-50/50 p-3.5 text-sm">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-amber-900/70 mb-1">
              Root Cause Hypothesis
            </h4>
            <p className="font-medium text-amber-950 leading-relaxed">
              {summary.root_cause_hypothesis}
            </p>
          </div>
        )}

        {summary.key_signals && Array.isArray(summary.key_signals) && summary.key_signals.length > 0 && (
          <div className="rounded-lg border border-neutral-200/80 bg-white p-3.5">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-neutral-400 mb-2">
              Key Diagnostic Signals
            </h4>
            <ul className="space-y-1.5">
              {summary.key_signals.map((sig: string, idx: number) => (
                <li key={idx} className="flex items-start gap-2 text-xs text-neutral-700">
                  <span className="text-emerald-500 font-bold">•</span>
                  <span>{sig}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {summary.affected_pods && Array.isArray(summary.affected_pods) && summary.affected_pods.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap text-xs">
            <span className="text-neutral-500 font-medium">Affected pods:</span>
            {summary.affected_pods.map((pod: string, idx: number) => (
              <span
                key={idx}
                className="font-mono bg-neutral-200/70 text-neutral-800 px-2 py-0.5 rounded text-[11px]"
              >
                {pod}
              </span>
            ))}
          </div>
        )}

        {/* Kubectl tools run */}
        {toolsExecuted.length > 0 && (
          <div
            className="rounded-lg border border-neutral-200/80 bg-white p-3"
            // Largest subtree of a context step — isolate its layout from the rest
            style={{ contentVisibility: 'auto', containIntrinsicSize: 'auto 240px' }}
          >
            <h4 className="text-xs font-semibold uppercase tracking-wider text-neutral-400 mb-2">
              Kubectl Commands Executed ({toolsExecuted.length})
            </h4>
            <div className="space-y-2">
              {toolsExecuted.map((cmd) => {
                const res = context[cmd]
                return (
                  <div key={cmd} className="rounded bg-neutral-900 text-neutral-100 p-2.5 text-xs font-mono overflow-x-auto">
                    <div className="flex items-center justify-between text-neutral-400 pb-1 border-b border-neutral-800 mb-1.5">
                      <span>$ kubectl {cmd.replace(':', ' ')}</span>
                      <span className={res?.ok ? 'text-emerald-400' : 'text-red-400'}>
                        {res?.ok ? 'OK (0)' : 'FAILED'}
                      </span>
                    </div>
                    {res?.output && (
                      <pre
                        className="text-neutral-300 text-[11px] whitespace-pre-wrap max-h-36 overflow-y-auto"
                        style={{ willChange: 'transform' }}
                      >
                        {typeof res.output === 'string' ? res.output : JSON.stringify(res.output, null, 2)}
                      </pre>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    )
  }

  if (isRoute && data.proposed_action) {
    return (
      <div className="rounded-lg border border-blue-200/70 bg-blue-50/50 p-3.5 text-sm text-blue-900">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-blue-700/70 mb-1">
          Route Decision
        </h4>
        <p className="font-medium">{data.proposed_action}</p>
      </div>
    )
  }

  // Fallback for any other output data
  if (Object.keys(data).length > 0) {
    return (
      <pre
        className="rounded-lg bg-neutral-900 p-3 text-[11px] font-mono text-neutral-200 overflow-x-auto max-h-40"
        style={{ willChange: 'transform' }}
      >
        {JSON.stringify(data, null, 2)}
      </pre>
    )
  }

  return null
})
