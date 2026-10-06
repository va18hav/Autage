import { Card, CardContent, CardHeader } from '@/components/ui/card'
import type { ContextSummary } from '../../../shared/types/incident'

export function ContextSummaryCard({ data }: { data: ContextSummary }) {
  return (
    <Card className="rounded-xl shadow-xs">
      <CardHeader className="border-b px-5 py-3.5">
        <h3 className="text-sm font-semibold text-neutral-800">Context summary</h3>
      </CardHeader>
      <CardContent className="px-5 py-4">
        <p className="text-sm leading-relaxed text-neutral-800">{data.root_cause_hypothesis}</p>

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
          <ol className="mt-4 space-y-1.5 border-t pt-4">
            {data.recommended_next_steps.map((step, i) => (
              <li key={i} className="flex gap-2 text-xs text-neutral-600">
                <span className="shrink-0 font-medium text-neutral-400">{i + 1}.</span>
                {step}
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  )
}
