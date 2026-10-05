import type { IncidentStatus } from '../types/incident'

const STATUS_STYLES: Record<IncidentStatus, { label: string; className: string; dot: string }> = {
  PENDING: {
    label: 'Pending',
    className: 'border-neutral-200 bg-neutral-50 text-neutral-600',
    dot: 'bg-neutral-400',
  },
  TRIAGING: {
    label: 'Triaging',
    className: 'border-amber-200 bg-amber-50 text-amber-700',
    dot: 'bg-amber-500',
  },
  COMPLETED: {
    label: 'Completed',
    className: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    dot: 'bg-emerald-500',
  },
  FAILED: {
    label: 'Failed',
    className: 'border-red-200 bg-red-50 text-red-700',
    dot: 'bg-red-500',
  },
}

export function StatusBadge({ status }: { status: IncidentStatus }) {
  const style = STATUS_STYLES[status]
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${style.className}`}
    >
      <span className={`size-1.5 rounded-full ${style.dot}`} />
      {style.label}
    </span>
  )
}
