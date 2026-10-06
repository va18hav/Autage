import { memo } from 'react'
import type { LiveStep } from '../store/incident-live-store'

/**
 * Rich renderer for a single node's output — shared by the live terminal and
 * the dashboard drawer timeline so both views display step data identically.
 * Memoized: incident refetches re-render parents without reworking every step.
 * Renders both the new step payloads (fetch_logs / refer_runbooks /
 * recommended_steps) and legacy rows stored under the old context_* schema.
 */
export const StepOutput = memo(function StepOutput({ step }: { step: LiveStep }) {
  const data = (step.output_data ?? {}) as Record<string, any>
  const isTriage = step.name === 'triage' || step.name === 'process_alert'
  const isLogs =
    step.name === 'fetch_logs' || step.name === 'context_gathering' || step.name === 'gather_context'
  const isRunbooks = step.name === 'refer_runbooks'
  const isRecommended = step.name === 'recommended_steps'
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

  if (isLogs) {
    const logsSummary = typeof data.logs_summary === 'string' ? data.logs_summary : null
    const logs: Record<string, any> = data.logs ?? {}
    const toolsExecuted = Object.keys(logs)
    const legacySummary = data.context_summary // legacy rows: structured ContextSummary object

    return (
      <div className="space-y-3">
        {/* Legacy stored rows (context_summary object + hypothesis/signals) */}
        {legacySummary && typeof legacySummary === 'object' && (
          <>
            {legacySummary.root_cause_hypothesis && (
              <div className="rounded-lg border border-amber-200/70 bg-amber-50/50 p-3.5 text-sm">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-amber-900/70 mb-1">
                  Root Cause Hypothesis
                </h4>
                <p className="font-medium text-amber-950 leading-relaxed">
                  {legacySummary.root_cause_hypothesis}
                </p>
              </div>
            )}
            {Array.isArray(legacySummary.key_signals) && legacySummary.key_signals.length > 0 && (
              <div className="rounded-lg border border-neutral-200/80 bg-white p-3.5">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-neutral-400 mb-2">
                  Key Diagnostic Signals
                </h4>
                <ul className="space-y-1.5">
                  {legacySummary.key_signals.map((sig: string, idx: number) => (
                    <li key={idx} className="flex items-start gap-2 text-xs text-neutral-700">
                      <span className="text-emerald-500 font-bold">•</span>
                      <span>{sig}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {Array.isArray(legacySummary.affected_pods) && legacySummary.affected_pods.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap text-xs">
                <span className="text-neutral-500 font-medium">Affected pods:</span>
                {legacySummary.affected_pods.map((pod: string, idx: number) => (
                  <span
                    key={idx}
                    className="font-mono bg-neutral-200/70 text-neutral-800 px-2 py-0.5 rounded text-[11px]"
                  >
                    {pod}
                  </span>
                ))}
              </div>
            )}
          </>
        )}

        {/* New fetch_logs payload: plain-text summary (+ runbooks request flag) */}
        {logsSummary && (
          <div className="rounded-lg border border-blue-200/70 bg-blue-50/40 p-3.5 text-sm">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-blue-800/70 mb-1.5">
              Logs Summary
            </h4>
            <p className="leading-relaxed text-neutral-800">{logsSummary}</p>
            {data.runbooks_needed === true && (
              <p className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-amber-100/70 px-2.5 py-0.5 text-xs font-medium text-amber-800">
                Runbooks requested for this incident
              </p>
            )}
          </div>
        )}

        {/* Kubectl tools run */}
        {toolsExecuted.length > 0 && (
          <div
            className="rounded-lg border border-neutral-200/80 bg-white p-3"
            // Largest subtree of a logs step — isolate its layout from the rest
            style={{ contentVisibility: 'auto', containIntrinsicSize: 'auto 240px' }}
          >
            <h4 className="text-xs font-semibold uppercase tracking-wider text-neutral-400 mb-2">
              Kubectl Commands Executed ({toolsExecuted.length})
            </h4>
            <div className="space-y-2">
              {toolsExecuted.map((cmd) => {
                const res = logs[cmd]
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

  if (isRunbooks) {
    const runbooks = typeof data.runbooks_summary === 'string' ? data.runbooks_summary : null
    if (runbooks) {
      return (
        <div className="rounded-lg border border-violet-200/70 bg-violet-50/40 p-3.5 text-sm">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-violet-800/70 mb-1.5">
            Runbook Findings
          </h4>
          <p className="leading-relaxed text-neutral-800">{runbooks}</p>
        </div>
      )
    }
    return null
  }

  if (isRecommended && Array.isArray(data.recommended_steps) && data.recommended_steps.length > 0) {
    return (
      <div className="rounded-lg border border-emerald-200/70 bg-emerald-50/50 p-3.5">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-emerald-800/70 mb-2">
          Recommended Steps
        </h4>
        <ol className="space-y-1.5">
          {data.recommended_steps.map((step: string, idx: number) => (
            <li key={idx} className="flex gap-2 text-xs leading-relaxed text-neutral-700">
              <span className="shrink-0 font-medium text-neutral-400">{idx + 1}.</span>
              {step}
            </li>
          ))}
        </ol>
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
