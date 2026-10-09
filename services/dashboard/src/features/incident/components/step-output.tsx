import { memo } from 'react'
import type { LiveStep } from '../store/incident-live-store'

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
          <p className="text-[15px] leading-relaxed text-neutral-800">{data.summary}</p>
        )}

        {data.description && data.description !== data.summary && (
          <p className="text-[14px] leading-relaxed text-neutral-600">
            {data.description}
          </p>
        )}
      </div>
    )
  }

  if (isLogs) {
    const logsSummary = typeof data.logs_summary === 'string' ? data.logs_summary : null
    const logs: Record<string, any> = data.logs ?? {}
    const toolsExecuted = Object.keys(logs)
    const legacySummary = data.context_summary

    return (
      <div className="space-y-4">
        {legacySummary && typeof legacySummary === 'object' && (
          <>
            {legacySummary.root_cause_hypothesis && (
              <div className="rounded-xl bg-neutral-50 p-4">
                <h4 className="mb-1 text-[13px] font-medium text-neutral-500">
                  Root Cause Hypothesis
                </h4>
                <p className="text-[14.5px] leading-relaxed text-neutral-900">
                  {legacySummary.root_cause_hypothesis}
                </p>
              </div>
            )}
            {Array.isArray(legacySummary.key_signals) && legacySummary.key_signals.length > 0 && (
              <ul className="space-y-2">
                {legacySummary.key_signals.map((sig: string, idx: number) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2.5 text-[14px] leading-relaxed text-neutral-700"
                  >
                    <span className="mt-2 size-1.5 shrink-0 rounded-full bg-neutral-400" />
                    <span>{sig}</span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}

        {logsSummary && (
          <div className="space-y-2">
            <p className="text-[15px] leading-relaxed text-neutral-800">{logsSummary}</p>
            {data.runbooks_needed === true && (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-neutral-100 px-3 py-1 text-[12.5px] font-medium text-neutral-700">
                <span className="size-1.5 rounded-full bg-amber-500" />
                Consulting operational runbooks
              </span>
            )}
          </div>
        )}

        {/* Gemini-inspired dark rounded terminal blocks for kubectl commands */}
        {toolsExecuted.length > 0 && (
          <div
            className="space-y-3 pt-1"
            style={{ contentVisibility: 'auto', containIntrinsicSize: 'auto 240px' }}
          >
            {toolsExecuted.map((cmd) => {
              const res = logs[cmd]
              return (
                <div
                  key={cmd}
                  className="overflow-hidden rounded-2xl bg-[#141414] text-neutral-100"
                >
                  <div className="flex items-center justify-between px-5 pt-3.5 pb-2 text-[12.5px]">
                    <span className="font-sans font-medium text-neutral-400">
                      kubectl {cmd.replace(':', ' ')}
                    </span>
                    <span
                      className={`font-mono text-[11.5px] font-medium ${
                        res?.ok ? 'text-emerald-400' : 'text-red-400'
                      }`}
                    >
                      {res?.ok ? 'OK' : 'Failed'}
                    </span>
                  </div>
                  {res?.output && (
                    <pre
                      className="max-h-52 overflow-y-auto px-5 pt-1 pb-4 font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap text-neutral-200"
                      style={{ willChange: 'transform' }}
                    >
                      {typeof res.output === 'string'
                        ? res.output
                        : JSON.stringify(res.output, null, 2)}
                    </pre>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    )
  }

  if (isRunbooks) {
    const runbooks = typeof data.runbooks_summary === 'string' ? data.runbooks_summary : null
    if (runbooks) {
      return <p className="text-[15px] leading-relaxed text-neutral-800">{runbooks}</p>
    }
    return null
  }

  if (isRecommended && Array.isArray(data.recommended_steps) && data.recommended_steps.length > 0) {
    return (
      <ol className="space-y-3">
        {data.recommended_steps.map((item: string, idx: number) => (
          <li
            key={idx}
            className="flex items-start gap-3 text-[15px] leading-relaxed text-neutral-800"
          >
            <span className="mt-0.5 shrink-0 font-medium text-neutral-400 tabular-nums">
              {idx + 1}.
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ol>
    )
  }

  if (isRoute && data.proposed_action) {
    return <p className="text-[15px] text-neutral-800">{data.proposed_action}</p>
  }

  if (Object.keys(data).length > 0) {
    return (
      <pre
        className="max-h-48 overflow-x-auto rounded-2xl bg-[#141414] p-4 font-mono text-[12.5px] leading-relaxed text-neutral-200"
        style={{ willChange: 'transform' }}
      >
        {JSON.stringify(data, null, 2)}
      </pre>
    )
  }

  return null
})
