import { useMemo } from 'react'
import { useNow } from '../../../shared/hooks/use-now'
import type { IncidentSummary } from '../../../shared/types/incident'

interface IncidentActivityCardProps {
  incidents: IncidentSummary[]
}

export function IncidentActivityCard({ incidents }: IncidentActivityCardProps) {
  const now = useNow(60_000)

  const { days, maxCount, stats, completionRate } = useMemo(() => {
    const dayBuckets: Array<{
      label: string
      shortLabel: string
      completed: number
      active: number
      failed: number
      total: number
    }> = []

    const byDateKey = new Map<
      string,
      { completed: number; active: number; failed: number }
    >()

    for (let i = 13; i >= 0; i--) {
      const d = new Date(now)
      d.setHours(0, 0, 0, 0)
      d.setDate(d.getDate() - i)
      const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
      byDateKey.set(key, { completed: 0, active: 0, failed: 0 })
      dayBuckets.push({
        label: d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
        shortLabel: d.toLocaleDateString(undefined, { day: 'numeric' }),
        completed: 0,
        active: 0,
        failed: 0,
        total: 0,
      })
    }

    const keys = Array.from(byDateKey.keys())
    let activeTotal = 0
    let completedTotal = 0
    let failedTotal = 0

    for (const inc of incidents) {
      if (inc.status === 'COMPLETED') completedTotal++
      else if (inc.status === 'FAILED') failedTotal++
      else activeTotal++

      const created = new Date(inc.created_at)
      const key = `${created.getFullYear()}-${created.getMonth()}-${created.getDate()}`
      const idx = keys.indexOf(key)
      if (idx !== -1) {
        if (inc.status === 'COMPLETED') dayBuckets[idx].completed++
        else if (inc.status === 'FAILED') dayBuckets[idx].failed++
        else dayBuckets[idx].active++
        dayBuckets[idx].total++
      }
    }

    const max = Math.max(1, ...dayBuckets.map((b) => b.total))
    const totalFinished = completedTotal + failedTotal
    const rate =
      totalFinished > 0 ? Math.round((completedTotal / totalFinished) * 100) : 100

    return {
      days: dayBuckets,
      maxCount: max,
      stats: {
        total: incidents.length,
        active: activeTotal,
        completed: completedTotal,
        failed: failedTotal,
      },
      completionRate: rate,
    }
  }, [incidents, now])

  return (
    <div className="flex flex-col justify-between rounded-2xl border border-neutral-200/80 bg-white p-6 lg:col-span-2">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[14px] font-medium text-neutral-500">
            Incident Volume & Analysis
          </p>
          <div className="mt-2 flex items-baseline gap-3">
            <span className="text-4xl font-semibold tracking-tight text-neutral-950 tabular-nums">
              {stats.total}
            </span>
            <span className="text-[14px] text-neutral-500">
              total incidents · {completionRate}% analyzed
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-[13px] font-medium text-emerald-800">
            <span className="size-2 rounded-full bg-emerald-500" />
            {stats.completed} Analyzed
          </span>
          {stats.active > 0 && (
            <span className="inline-flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1 text-[13px] font-medium text-amber-800">
              <span className="size-2 rounded-full bg-amber-500 animate-pulse" />
              {stats.active} Active
            </span>
          )}
          {stats.failed > 0 && (
            <span className="inline-flex items-center gap-2 rounded-full bg-red-50 px-3 py-1 text-[13px] font-medium text-red-700">
              <span className="size-2 rounded-full bg-red-500" />
              {stats.failed} Failed
            </span>
          )}
        </div>
      </div>

      {/* 14-Day Bar Chart */}
      <div className="mt-8">
        <div className="flex h-32 items-end gap-2">
          {days.map((day) => {
            const heightPct =
              day.total === 0 ? 6 : Math.max(14, Math.round((day.total / maxCount) * 100))

            return (
              <div
                key={day.label}
                className="group relative flex h-full flex-1 flex-col items-center justify-end"
                title={`${day.label}: ${day.total} ${day.total === 1 ? 'incident' : 'incidents'}`}
              >
                <div
                  className={`w-full rounded-t-md transition-colors duration-150 ${
                    day.total === 0
                      ? 'bg-neutral-100 group-hover:bg-neutral-200'
                      : day.active > 0
                        ? 'bg-amber-500'
                        : 'bg-neutral-900 group-hover:bg-neutral-700'
                  }`}
                  style={{ height: `${heightPct}%` }}
                />
                <span className="mt-2 text-[11px] text-neutral-400 tabular-nums">
                  {day.shortLabel}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
