import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronRight, CircleX, Inbox, ShieldCheck, Waves, FileBarChart2 } from 'lucide-react'

import { useIncidentList } from './hooks/use-incidents'
import { useIncidentDetail } from './hooks/use-incident-detail'
import { IncidentRow } from './components/incident-row'
import { StepTimeline } from './components/step-timeline'
import { StatusBadge } from '../../shared/components/status-badge'
import { TimeAgo } from '../../shared/components/time-ago'
import { incidentApi } from '../../shared/lib/api'
import { queryKeys } from '../../shared/lib/query-client'
import type { IncidentSummary } from '../../shared/types/incident'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
  Button,
  Card,
  Separator,
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  Skeleton,
} from '@/components/ui'

const ONGOING: IncidentSummary['status'][] = ['PENDING', 'TRIAGING']

export function DashboardPage() {
  const { data: incidents, isPending, isError } = useIncidentList()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { ongoing, past, stats } = useMemo(() => {
    const ongoing = (incidents ?? []).filter((i) => ONGOING.includes(i.status))
    const past = (incidents ?? []).filter((i) => !ONGOING.includes(i.status))
    return {
      ongoing,
      past,
      stats: {
        total: incidents?.length ?? 0,
        ongoing: ongoing.length,
        resolved: past.length,
      },
    }
  }, [incidents])

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Incidents</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Live SRE copilot — triage, diagnostics and remediation
          </p>
        </div>
      </header>

      {/* At a glance */}
      <div className="grid gap-4 sm:grid-cols-3">
        <MetricCard
          icon={<Waves className="size-4 text-amber-600" />}
          label="Ongoing incidents"
          value={stats.ongoing}
          hint="Pending or triaging right now"
        />
        <MetricCard
          icon={<ShieldCheck className="size-4 text-emerald-600" />}
          label="Resolved"
          value={stats.resolved}
          hint="Closed with recommended steps"
        />
        <MetricCard
          icon={<FileBarChart2 className="size-4 text-neutral-500" />}
          label="Tracked this page"
          value={stats.total}
          hint="All incidents in view"
        />
      </div>

      {isPending && (
        <div className="space-y-2 rounded-xl border bg-card shadow-xs">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-5 py-4">
              <Skeleton className="h-4 w-2/3 max-w-md" />
              <Skeleton className="ml-auto h-5 w-20" />
            </div>
          ))}
        </div>
      )}

      {isError && (
        <p className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
          Couldn&apos;t load incidents. Is the API running on port 8000?
        </p>
      )}

      {incidents && (
        <>
          <IncidentSection
            icon={<Waves className="size-3.5" />}
            title="Ongoing"
            count={stats.ongoing}
            isEmpty={stats.ongoing === 0}
          >
            {ongoing.map((incident) => (
              <IncidentRow
                key={incident.id}
                incident={incident}
                onOpen={(i) => setSelectedId(i.id)}
              />
            ))}
          </IncidentSection>

          <IncidentSection
            icon={<ShieldCheck className="size-3.5" />}
            title="Previous"
            count={past.length}
            isEmpty={past.length === 0}
          >
            {past.map((incident) => (
              <IncidentRow
                key={incident.id}
                incident={incident}
                onOpen={(i) => setSelectedId(i.id)}
              />
            ))}
          </IncidentSection>
        </>
      )}

      <IncidentSheet id={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  )
}

function MetricCard({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ReactNode
  label: string
  value: number
  hint: string
}) {
  return (
    <Card className="gap-0 px-5 py-4 transition-shadow hover:shadow-md">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        {icon}
        {label}
      </div>
      <p className="mt-1.5 text-3xl font-semibold tracking-tight tabular-nums">{value}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>
    </Card>
  )
}

function IncidentSection({
  title,
  count,
  isEmpty,
  icon,
  children,
}: {
  title: string
  count: number
  isEmpty: boolean
  icon: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <section>
      <h2 className="mb-3 flex items-center gap-2 text-sm font-medium text-muted-foreground">
        <span className="[&>svg]:size-3.5">{icon}</span>
        {title} · {count}
      </h2>
      {isEmpty ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed bg-card px-5 py-10 text-center">
          <Inbox className="size-5 text-muted-foreground/60" />
          <p className="text-sm text-muted-foreground">Nothing here</p>
        </div>
      ) : (
        <div className="divide-y divide-border overflow-hidden rounded-xl border bg-card shadow-xs">
          {children}
        </div>
      )}
    </section>
  )
}

function IncidentSheet({ id, onClose }: { id: string | null; onClose: () => void }) {
  const { data: incident } = useIncidentDetail(id ?? '')
  const queryClient = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: () => incidentApi.delete(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.incidents.all })
      onClose()
    },
  })

  const nextSteps = incident ? extractRecommendedNextSteps(incident) : null

  return (
    <Sheet open={id != null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        side="right"
        className="flex w-full flex-col gap-0 p-0 data-[side=right]:sm:max-w-3xl data-[side=right]:lg:max-w-4xl data-[side=right]:xl:max-w-5xl"
      >
        {incident ? (
          <>
            <SheetHeader className="border-b px-8 py-6 text-left">
              <div className="flex items-start justify-between gap-4 pr-10">
                <div className="min-w-0">
                  <StatusBadge status={incident.status} />
                  <SheetTitle asChild>
                    <h2 className="mt-3 text-lg font-semibold leading-snug tracking-tight">
                      {incident.title}
                    </h2>
                  </SheetTitle>
                  <SheetDescription asChild>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Opened <TimeAgo date={incident.created_at} />
                    </p>
                  </SheetDescription>
                </div>
              </div>
            </SheetHeader>

            <div className="flex-1 space-y-8 overflow-y-auto overscroll-contain px-8 py-6" style={{ willChange: 'scroll-position' }}>
              {(incident.status === 'PENDING' || incident.status === 'TRIAGING') && (
                <div className="rounded-xl border bg-amber-50/60 px-5 py-4">
                  <p className="text-sm font-medium text-amber-900">Agent still working</p>
                  <p className="mt-1 text-xs text-amber-800/70">
                    Watch the triage unfold in real time.
                  </p>
                  <Button asChild size="sm" variant="secondary" className="mt-3">
                    <Link to={`/incidents/${incident.id}/live`}>
                      Open live view
                      <ChevronRight className="size-4" />
                    </Link>
                  </Button>
                </div>
              )}

              {nextSteps && nextSteps.length > 0 && (
                <section>
                  <h3 className="mb-3 text-sm font-medium text-muted-foreground">
                    Recommended steps
                  </h3>
                  <ol className="space-y-1.5 rounded-lg border bg-white p-4 text-sm leading-relaxed text-neutral-700">
                    {nextSteps.map((step, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="shrink-0 text-muted-foreground">{i + 1}.</span>
                        {step}
                      </li>
                    ))}
                  </ol>
                </section>
              )}

              <section>
                <h3 className="mb-3 text-sm font-medium text-muted-foreground">Agent steps</h3>
                <StepTimeline steps={incident.steps} />
              </section>
            </div>

            <Separator />
            <footer className="flex items-center justify-between px-8 py-3.5">
              <span className="font-mono text-[11px] text-muted-foreground">{incident.id}</span>
              <DeleteRunbookButton
                onConfirm={() => deleteMutation.mutate()}
                pending={deleteMutation.isPending}
              />
            </footer>
          </>
        ) : (
          <div className="flex flex-1 flex-col gap-6 px-8 py-8">
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-8 w-3/4" />
            <Skeleton className="h-4 w-1/3" />
            <Separator />
            <div className="space-y-3">
              <Skeleton className="h-4 w-1/3" />
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-4 w-2/3" />
              ))}
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}

function DeleteRunbookButton({
  onConfirm,
  pending,
}: {
  onConfirm: () => void
  pending: boolean
}) {
  const [open, setOpen] = useState(false)

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="gap-1.5 text-red-600 hover:bg-red-50 hover:text-red-700"
        >
          <CircleX className="size-4" />
          Delete incident
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete this incident?</AlertDialogTitle>
          <AlertDialogDescription>
            This permanently removes the incident and all of its recorded agent
            steps. This action cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            disabled={pending}
            className="bg-red-600 text-white hover:bg-red-700"
          >
            {pending ? 'Deleting…' : 'Delete'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

function extractRecommendedNextSteps(
  incident: NonNullable<ReturnType<typeof useIncidentDetail>['data']>,
): string[] | null {
  const persisted = incident.recommended_steps
  if (Array.isArray(persisted) && persisted.every((s) => typeof s === 'string')) {
    return persisted
  }

  // Older incidents: fall back to the context_gathering step output
  for (const step of incident.steps) {
    if (step.step_name !== 'context_gathering' && step.step_name !== 'gather_context') continue
    const next = (step.output_data as { context_summary?: { recommended_next_steps?: unknown } } | null)
      ?.context_summary?.recommended_next_steps
    if (Array.isArray(next) && next.every((s) => typeof s === 'string')) {
      return next as string[]
    }
  }

  return null
}
