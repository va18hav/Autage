import { useState } from 'react'
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
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  Skeleton,
} from '@/components/ui'
import { Trash2 } from 'lucide-react'
import { useRunbookDetail } from '../hooks/use-runbooks'
import { TimeAgo } from '../../../shared/components/time-ago'

interface RunbookDetailSheetProps {
  runbookId: string | null
  onClose: () => void
  onDelete: (id: string) => void
}

export function RunbookDetailSheet({
  runbookId,
  onClose,
  onDelete,
}: RunbookDetailSheetProps) {
  const { data: runbook, isPending } = useRunbookDetail(runbookId)
  const [activeTab, setActiveTab] = useState<'sections' | 'raw'>('sections')

  return (
    <Sheet open={Boolean(runbookId)} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        side="right"
        className="flex w-full flex-col gap-0 bg-white p-0 data-[side=right]:w-full data-[side=right]:sm:max-w-2xl data-[side=right]:lg:max-w-3xl"
      >
        {isPending ? (
          <div className="space-y-4 p-8">
            <Skeleton className="h-6 w-1/3 rounded-full" />
            <Skeleton className="h-7 w-3/4" />
            <div className="mt-6 space-y-4">
              <Skeleton className="h-24 w-full rounded-2xl" />
              <Skeleton className="h-24 w-full rounded-2xl" />
              <Skeleton className="h-24 w-full rounded-2xl" />
            </div>
          </div>
        ) : runbook ? (
          <>
            <SheetHeader className="border-b border-neutral-200/70 px-5 py-5 text-left sm:px-8 sm:py-6">
              <div className="flex flex-wrap items-center gap-2 pr-8">
                {runbook.service && (
                  <span className="rounded-full bg-neutral-100 px-3 py-1 text-[12.5px] font-medium text-neutral-700">
                    {runbook.service}
                  </span>
                )}
                <span className="rounded-full bg-neutral-100 px-3 py-1 text-[12.5px] font-medium text-neutral-600">
                  {runbook.sections.length} {runbook.sections.length === 1 ? 'section' : 'sections'}
                </span>
              </div>

              <SheetTitle className="mt-3.5 text-xl font-semibold leading-snug tracking-tight text-neutral-950">
                {runbook.title}
              </SheetTitle>

              <SheetDescription className="mt-1.5 text-[13.5px] text-neutral-500">
                Created <TimeAgo date={runbook.created_at} /> · Updated{' '}
                <TimeAgo date={runbook.updated_at} />
              </SheetDescription>

              {runbook.triggers && runbook.triggers.length > 0 && (
                <div className="mt-3.5 flex flex-wrap items-center gap-2">
                  <span className="text-[13px] text-neutral-400">Triggers:</span>
                  {runbook.triggers.map((trigger) => (
                    <span
                      key={trigger}
                      className="inline-flex items-center rounded-full border border-neutral-200/80 bg-neutral-50 px-2.5 py-0.5 font-mono text-[12px] text-neutral-700"
                    >
                      {trigger}
                    </span>
                  ))}
                </div>
              )}
            </SheetHeader>

            {/* Sub-navigation & delete bar */}
            <div className="flex items-center justify-between border-b border-neutral-100 bg-white px-5 py-3 sm:px-8">
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => setActiveTab('sections')}
                  className={`cursor-pointer rounded-full px-4 py-1.5 text-[13.5px] font-medium transition-colors duration-100 ${
                    activeTab === 'sections'
                      ? 'bg-neutral-900 text-white'
                      : 'bg-neutral-100/80 text-neutral-600 hover:bg-neutral-200/70 hover:text-neutral-900'
                  }`}
                >
                  Sections ({runbook.sections.length})
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('raw')}
                  className={`cursor-pointer rounded-full px-4 py-1.5 text-[13.5px] font-medium transition-colors duration-100 ${
                    activeTab === 'raw'
                      ? 'bg-neutral-900 text-white'
                      : 'bg-neutral-100/80 text-neutral-600 hover:bg-neutral-200/70 hover:text-neutral-900'
                  }`}
                >
                  Raw Markdown
                </button>
              </div>

              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="gap-1.5 rounded-full px-3 text-neutral-500 hover:bg-red-50 hover:text-red-600"
                  >
                    <Trash2 className="size-4" />
                    Delete
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Delete this runbook?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This will permanently remove &ldquo;{runbook.title}&rdquo; and all of its
                      associated sections. The SRE agent will no longer be able to reference it
                      during incidents.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      className="bg-red-600 text-white hover:bg-red-700"
                      onClick={() => onDelete(runbook.id)}
                    >
                      Delete Runbook
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>

            <div className="flex-1 space-y-5 overflow-y-auto px-5 py-6 sm:px-8">
              {runbook.description && (
                <div className="rounded-2xl border border-neutral-200/80 bg-neutral-50/40 px-5 py-4">
                  <p className="text-[14.5px] leading-relaxed text-neutral-700">
                    {runbook.description}
                  </p>
                </div>
              )}

              {activeTab === 'sections' ? (
                <div className="space-y-4">
                  {runbook.sections.map((section) => (
                    <div
                      key={section.id}
                      className="overflow-hidden rounded-2xl border border-neutral-200/80 bg-white"
                    >
                      <div className="flex items-center justify-between gap-3 border-b border-neutral-100 px-5 py-3.5">
                        <div className="flex items-center gap-3">
                          <span className="flex size-6 items-center justify-center rounded-full bg-neutral-100 text-xs font-medium text-neutral-600 tabular-nums">
                            {section.order_index + 1}
                          </span>
                          <h4 className="text-[15px] font-semibold text-neutral-900">
                            {section.heading}
                          </h4>
                        </div>
                        <span className="text-[12.5px] text-neutral-400 tabular-nums">
                          {section.content.length} chars
                        </span>
                      </div>
                      <div className="p-5">
                        <pre className="max-h-72 overflow-x-auto font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap text-neutral-800">
                          {section.content}
                        </pre>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="overflow-hidden rounded-2xl bg-[#141414] p-5">
                  <pre className="overflow-x-auto font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap text-neutral-200">
                    {runbook.raw_content}
                  </pre>
                </div>
              )}
            </div>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
