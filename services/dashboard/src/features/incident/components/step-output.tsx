import { memo } from 'react'
import type { Diagnosis } from '../../../shared/types/incident'
import type { LiveStep } from '../store/incident-live-store'

interface EvidenceRecord {
  tool: string
  scope: string
  target: string
  ok: boolean
  output: string
  error: string | null
  truncated: boolean
}

const INCIDENT_TYPE_LABELS: Record<string, string> = {
  crash_loop: 'Crash loop',
  bad_deployment: 'Bad deployment',
  other: 'Other',
}

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null
}

function isEvidenceRecord(value: unknown): value is EvidenceRecord {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return (
    typeof record.tool === 'string' &&
    typeof record.target === 'string' &&
    typeof record.ok === 'boolean' &&
    typeof record.output === 'string'
  )
}

function isDiagnosis(value: unknown): value is Diagnosis {
  if (!value || typeof value !== 'object') return false
  const diagnosis = value as Record<string, unknown>
  return (
    typeof diagnosis.what_happened === 'string' &&
    typeof diagnosis.likely_cause === 'string' &&
    Array.isArray(diagnosis.recommended_steps)
  )
}

function EvidenceBlock({ record }: { record: EvidenceRecord }) {
  return (
    <div className="overflow-hidden rounded-2xl bg-[#141414] text-neutral-100">
      <div className="flex items-center justify-between gap-4 px-5 pt-3.5 pb-2 text-[12.5px]">
        <span className="font-sans font-medium text-neutral-400">
          {record.tool.replaceAll('_', ' ')}
          <span className="ml-2 text-neutral-500">{record.target}</span>
        </span>
        <span
          className={`shrink-0 font-mono text-[11.5px] font-medium ${
            record.ok ? 'text-emerald-400' : 'text-red-400'
          }`}
        >
          {record.ok ? 'OK' : 'Failed'}
        </span>
      </div>
      {record.output && (
        <pre className="max-h-52 overflow-y-auto px-5 pt-1 pb-4 font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap text-neutral-200">
          {record.output}
        </pre>
      )}
      {record.error && (
        <p className="border-t border-neutral-800 px-5 py-3 font-mono text-[12px] leading-relaxed text-red-300">
          {record.error}
        </p>
      )}
      {record.truncated && (
        <p className="px-5 pb-3 text-[12px] text-neutral-500">Output was truncated.</p>
      )}
    </div>
  )
}

function MissingEvidence({ data }: { data: Record<string, unknown> }) {
  const missing = Array.isArray(data.missing_evidence)
    ? data.missing_evidence.filter((item): item is string => typeof item === 'string')
    : []

  if (missing.length === 0) return null

  return (
    <div className="rounded-xl border border-amber-200/80 bg-amber-50/60 p-4">
      <h4 className="mb-2 text-[13px] font-medium text-amber-900">
        Missing or incomplete evidence
      </h4>
      <ul className="space-y-1.5">
        {missing.map((item, i) => (
          <li key={i} className="flex gap-2.5 text-[13.5px] leading-relaxed text-amber-900/90">
            <span className="mt-2 size-1.5 shrink-0 rounded-full bg-amber-500" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export const StepOutput = memo(function StepOutput({ step }: { step: LiveStep }) {
  const data = (step.output_data ?? {}) as Record<string, unknown>

  if (step.name === 'triage') {
    const summary = text(data.summary)
    const description = text(data.description)
    const incidentType = text(data.incident_type)
    const target = [text(data.namespace), text(data.pod_name) ?? text(data.deployment_name)]
      .filter(Boolean)
      .join(' / ')

    if (!summary && !description) return null

    return (
      <div className="space-y-3">
        {summary && <p className="text-[15px] leading-relaxed text-neutral-800">{summary}</p>}
        {description && description !== summary && (
          <p className="text-[14px] leading-relaxed text-neutral-600">{description}</p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          {incidentType && (
            <span className="inline-flex items-center rounded-full bg-neutral-100 px-3 py-1 text-[12.5px] font-medium text-neutral-700">
              {INCIDENT_TYPE_LABELS[incidentType] ?? incidentType}
            </span>
          )}
          {target && (
            <span className="font-mono text-[12.5px] text-neutral-500">{target}</span>
          )}
        </div>
      </div>
    )
  }

  if (step.name === 'collect_evidence') {
    const evidence = Array.isArray(data.evidence)
      ? data.evidence.filter(isEvidenceRecord)
      : []
    const succeeded = evidence.filter((record) => record.ok).length

    return (
      <div className="space-y-4">
        {evidence.length > 0 && (
          <p className="text-[14px] text-neutral-600">
            {succeeded} of {evidence.length} read-only checks succeeded.
          </p>
        )}
        {evidence.length > 0 && (
          <div className="space-y-3">
            {evidence.map((record, i) => (
              <EvidenceBlock key={`${record.tool}-${record.target}-${i}`} record={record} />
            ))}
          </div>
        )}
        <MissingEvidence data={data} />
      </div>
    )
  }

  if (step.name === 'find_runbook') {
    const summary = text(data.runbooks_summary)

    return (
      <div className="space-y-4">
        {summary ? (
          <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-neutral-700">
            {summary}
          </p>
        ) : (
          <p className="text-[14px] text-neutral-500">No matching runbook sections were found.</p>
        )}
        <MissingEvidence data={data} />
      </div>
    )
  }

  if (step.name === 'diagnose') {
    const diagnosis = data.diagnosis

    if (isDiagnosis(diagnosis)) {
      return (
        <div className="space-y-2">
          <p className="text-[15px] leading-relaxed text-neutral-800">
            {diagnosis.what_happened}
          </p>
          <p className="text-[14px] leading-relaxed text-neutral-600">
            <span className="font-medium text-neutral-700">Likely cause:</span>{' '}
            {diagnosis.likely_cause}
          </p>
        </div>
      )
    }
  }

  if (Object.keys(data).length > 0) {
    return (
      <pre className="max-h-48 overflow-x-auto rounded-2xl bg-[#141414] p-4 font-mono text-[12.5px] leading-relaxed text-neutral-200">
        {JSON.stringify(data, null, 2)}
      </pre>
    )
  }

  return null
})
