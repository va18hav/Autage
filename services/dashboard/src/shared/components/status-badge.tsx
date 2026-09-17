import { cn } from '@/lib/utils'
import type { IncidentStatus } from '../types/incident'

const STATUS_STYLES: Record<
  IncidentStatus,
  { label: string; className: string; dot: string; pulse?: boolean }
> = {
  PENDING: {
    label: 'Queued',
    className: 'bg-neutral-100 text-neutral-700',
    dot: 'bg-neutral-400',
  },
  TRIAGING: {
    label: 'Triaging',
    className: 'bg-amber-50 text-amber-800 ring-1 ring-amber-200/80',
    dot: 'bg-amber-500',
    pulse: true,
  },
  COMPLETED: {
    label: 'Resolved',
    className: 'bg-emerald-50 text-emerald-800 ring-1 ring-emerald-200/70',
    dot: 'bg-emerald-500',
  },
  FAILED: {
    label: 'Failed',
    className: 'bg-red-50 text-red-700 ring-1 ring-red-200/70',
    dot: 'bg-red-500',
  },
}

export function StatusBadge({ status }: { status: IncidentStatus }) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.PENDING
  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-full px-3 py-1 text-[12.5px] font-medium select-none',
        style.className,
      )}
    >
      <span className="relative flex size-2 shrink-0">
        {style.pulse && (
          <span
            className={cn(
              'absolute inline-flex size-full animate-ping rounded-full opacity-75',
              style.dot,
            )}
          />
        )}
        <span className={cn('relative inline-flex size-2 rounded-full', style.dot)} />
      </span>
      {style.label}
    </span>
  )
}
