import type { ContextSummary } from '../../../shared/types/incident'

export function ContextSummaryCard({ data }: { data: ContextSummary }) {
  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-5">
      <h3 className="text-sm font-medium text-neutral-500">Context summary</h3>
      <p className="mt-2 text-sm leading-relaxed text-neutral-800">{data.root_cause_hypothesis}</p>

      {data.key_signals.length > 0 && (
        <ul className="mt-4 space-y-1.5">
          {data.key_signals.map((signal, i) => (
            <li key={i} className="flex gap-2 text-xs text-neutral-600">
              <span className="mt-1.5 size-1 shrink-0 rounded-full bg-neutral-400" />
              {signal}
            </li>
          ))}
        </ul>
      )}

      {data.recommended_next_steps.length > 0 && (
        <ol className="mt-4 space-y-1.5 border-t border-neutral-100 pt-4">
          {data.recommended_next_steps.map((step, i) => (
            <li key={i} className="flex gap-2 text-xs text-neutral-600">
              <span className="shrink-0 font-medium text-neutral-400">{i + 1}.</span>
              {step}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
