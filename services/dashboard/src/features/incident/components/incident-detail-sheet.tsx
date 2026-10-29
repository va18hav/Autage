import { Link } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowUpRight } from 'lucide-react'

import { useIncidentDetail } from '../../dashboard/hooks/use-incident-detail'
import { StepTimeline } from '../../dashboard/components/step-timeline'
import { StatusBadge } from '../../../shared/components/status-badge'
import { TimeAgo } from '../../../shared/components/time-ago'
import { incidentApi } from '../../../shared/lib/api'
import { queryKeys } from '../../../shared/lib/query-client'
import {
  Separator,
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  Skeleton,
} from '@/components/ui'
import { DeleteIncidentDialog } from './delete-incident-dialog'
import { DiagnosisCard } from './diagnosis-card'

interface IncidentDetailSheetProps {
  incidentId: string | null
  onClose: () => void
}

export function IncidentDetailSheet({ incidentId, onClose }: IncidentDetailSheetProps) {
  const { data: incident } = useIncidentDetail(incidentId ?? '')
  const queryClient = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: () => incidentApi.delete(incidentId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.incidents.all })
      onClose()
    },
  })

  const analysis = incident?.analysis ?? null

  return (
    <Sheet open={incidentId != null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        side="right"
        className="flex w-full flex-col gap-0 bg-white p-0 data-[side=right]:w-full data-[side=right]:sm:max-w-2xl data-[side=right]:lg:max-w-3xl"
      >
        {incident ? (
          <>
            <SheetHeader className="border-b border-neutral-200/70 px-5 py-5 text-left sm:px-8 sm:py-6">
              <div className="flex flex-wrap items-center justify-between gap-3 pr-8">
                <StatusBadge status={incident.status} />

                <Link
                  to={`/incidents/${incident.id}/live`}
                  className="inline-flex items-center gap-1.5 rounded-full border border-neutral-200 bg-white px-4 py-1.5 text-[13px] font-medium text-neutral-800 transition-colors duration-100 hover:bg-neutral-50"
                >
                  <span>Open live view</span>
                  <ArrowUpRight className="size-3.5 text-neutral-500" />
                </Link>
              </div>

              <SheetTitle asChild>
                <h2 className="mt-4 text-xl font-semibold leading-snug tracking-tight text-neutral-950">
                  {incident.title}
                </h2>
              </SheetTitle>
              <SheetDescription asChild>
                <p className="mt-1.5 text-[13.5px] text-neutral-500">
                  Opened <TimeAgo date={incident.created_at} /> · Updated{' '}
                  <TimeAgo date={incident.updated_at} />
                </p>
              </SheetDescription>
            </SheetHeader>

            <div
              className="flex-1 space-y-7 overflow-y-auto overscroll-contain px-5 py-6 sm:space-y-8 sm:px-8 sm:py-7"
              style={{ willChange: 'scroll-position' }}
            >
              {(incident.status === 'PENDING' || incident.status === 'TRIAGING') && (
                <div className="flex items-center justify-between gap-4 rounded-2xl border border-amber-200/80 bg-amber-50/60 px-6 py-4">
                  <div className="flex items-center gap-3">
                    <span className="relative flex size-2.5 shrink-0">
                      <span className="absolute inline-flex size-full animate-ping rounded-full bg-amber-500 opacity-75" />
                      <span className="relative inline-flex size-2.5 rounded-full bg-amber-500" />
                    </span>
                    <div>
                      <p className="text-[14.5px] font-medium text-amber-950">
                        Agent is actively triaging this incident
                      </p>
                      <p className="text-[13px] text-amber-800/80">
                        Watch diagnostic steps and cluster telemetry stream in real time.
                      </p>
                    </div>
                  </div>
                  <Link
                    to={`/incidents/${incident.id}/live`}
                    className="shrink-0 rounded-full bg-neutral-900 px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-neutral-800"
                  >
                    Watch live
                  </Link>
                </div>
              )}

              {analysis && <DiagnosisCard diagnosis={analysis} />}

              <section>
                <h3 className="mb-4 text-[15px] font-semibold text-neutral-900">
                  Agent Execution Trace
                </h3>
                <StepTimeline steps={incident.steps} />
              </section>

              {incident.raw_alert && Object.keys(incident.raw_alert).length > 0 && (
                <section className="pt-2">
                  <details className="group overflow-hidden rounded-2xl border border-neutral-200/80 bg-neutral-50/40">
                    <summary className="flex cursor-pointer list-none items-center justify-between px-5 py-3.5 text-[14px] font-medium text-neutral-700 hover:text-neutral-950">
                      <span>Raw Alert Payload</span>
                      <span className="text-[13px] text-neutral-400 group-open:hidden">
                        Show JSON
                      </span>
                      <span className="hidden text-[13px] text-neutral-400 group-open:inline">
                        Hide
                      </span>
                    </summary>
                    <div className="border-t border-neutral-200/70 p-4">
                      <pre className="max-h-72 overflow-auto rounded-xl bg-[#141414] p-4 font-mono text-[12.5px] leading-relaxed text-neutral-200">
                        {JSON.stringify(incident.raw_alert, null, 2)}
                      </pre>
                    </div>
                  </details>
                </section>
              )}
            </div>

            <Separator />
            <footer className="flex flex-wrap items-center justify-between gap-2 px-5 py-3.5 sm:px-8 sm:py-4">
              <span className="truncate font-mono text-xs text-neutral-400">{incident.id}</span>
              <DeleteIncidentDialog
                onConfirm={() => deleteMutation.mutate()}
                pending={deleteMutation.isPending}
              />
            </footer>
          </>
        ) : (
          <div className="flex flex-1 flex-col gap-5 px-8 py-8">
            <Skeleton className="h-6 w-28 rounded-full" />
            <Skeleton className="h-7 w-3/4" />
            <Skeleton className="h-4 w-1/3" />
            <Separator />
            <div className="space-y-4">
              <Skeleton className="h-5 w-1/4" />
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-20 w-full rounded-2xl" />
              ))}
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
