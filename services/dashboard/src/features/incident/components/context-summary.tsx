import type { ContextSummary } from '../../../shared/types/incident'

export function ContextSummaryCard({ data }: { data: ContextSummary }) {
  return (
    <div className="rounded-2xl border border-neutral-200/80 bg-white p-6">
      <h3 className="text-[16px] font-semibold text-neutral-900">
        Diagnostic Context Summary
      </h3>
      <p className="mt-2.5 text-[15px] leading-relaxed text-neutral-800">
        {data.root_cause_hypothesis}
      </p>

      {data.key_signals.length > 0 && (
        <ul className="mt-4 space-y-2">
          {data.key_signals.map((signal, i) => (
            <li key={i} className="flex gap-2.5 text-[14px] text-neutral-600">
              <span className="mt-2 size-1.5 shrink-0 rounded-full bg-neutral-400" />
              {signal}
            </li>
          ))}
        </ul>
      )}

      {data.recommended_next_steps.length > 0 && (
        <ol className="mt-5 space-y-2.5 border-t border-neutral-100 pt-4">
          {data.recommended_next_steps.map((step, i) => (
            <li key={i} className="flex gap-3 text-[14px] text-neutral-800">
              <span className="shrink-0 font-medium text-neutral-400 tabular-nums">
                {i + 1}.
              </span>
              {step}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
