import type { Confidence, Diagnosis } from '../../../shared/types/incident'

const CONFIDENCE_STYLES: Record<Confidence, string> = {
  high: 'border-emerald-200/80 bg-emerald-50 text-emerald-800',
  medium: 'border-amber-200/80 bg-amber-50 text-amber-800',
  low: 'border-neutral-200 bg-neutral-100 text-neutral-600',
}

const CONFIDENCE_LABELS: Record<Confidence, string> = {
  high: 'High confidence',
  medium: 'Medium confidence',
  low: 'Low confidence',
}

export function DiagnosisCard({ diagnosis }: { diagnosis: Diagnosis }) {
  return (
    <section className="rounded-2xl border border-neutral-200/80 bg-white p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-[16px] font-semibold tracking-tight text-neutral-900">
          Diagnosis
        </h2>
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[12.5px] font-medium ${CONFIDENCE_STYLES[diagnosis.confidence]}`}
        >
          <span className="size-1.5 rounded-full bg-current opacity-70" />
          {CONFIDENCE_LABELS[diagnosis.confidence]}
        </span>
      </div>

      <div className="mt-4 grid gap-5 sm:grid-cols-2">
        <div>
          <h3 className="text-[13px] font-medium text-neutral-500">What happened</h3>
          <p className="mt-1.5 text-[14.5px] leading-relaxed text-neutral-800">
            {diagnosis.what_happened}
          </p>
        </div>
        <div>
          <h3 className="text-[13px] font-medium text-neutral-500">Likely cause</h3>
          <p className="mt-1.5 text-[14.5px] leading-relaxed text-neutral-800">
            {diagnosis.likely_cause}
          </p>
        </div>
      </div>

      {diagnosis.what_i_found && (
        <div className="mt-5 rounded-xl bg-neutral-50 p-4">
          <h3 className="text-[13px] font-medium text-neutral-500">What I found</h3>
          <p className="mt-1.5 text-[14px] leading-relaxed text-neutral-700">
            {diagnosis.what_i_found}
          </p>
        </div>
      )}

      {diagnosis.missing_information.length > 0 && (
        <div className="mt-5">
          <h3 className="text-[13px] font-medium text-neutral-500">Missing information</h3>
          <ul className="mt-2 space-y-2">
            {diagnosis.missing_information.map((item, i) => (
              <li key={i} className="flex gap-2.5 text-[14px] leading-relaxed text-neutral-600">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-amber-500" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {diagnosis.recommended_steps.length > 0 && (
        <div className="mt-5 border-t border-neutral-100 pt-5">
          <h3 className="text-[15px] font-semibold text-neutral-900">Recommended next steps</h3>
          <ol className="mt-3 divide-y divide-neutral-100">
            {diagnosis.recommended_steps.map((step, i) => (
              <li
                key={i}
                className="flex items-start gap-3.5 py-3 text-[14.5px] leading-relaxed text-neutral-800 first:pt-0 last:pb-0"
              >
                <span className="mt-0.5 shrink-0 font-medium text-neutral-400 tabular-nums">
                  {i + 1}.
                </span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  )
}
