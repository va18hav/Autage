import { ChevronRight, Trash2 } from 'lucide-react'
import { NavRunbooksIcon } from '../../../shared/components/icons'
import type { RunbookSummary } from '../../../shared/types/runbook'
import { TimeAgo } from '../../../shared/components/time-ago'
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
} from '@/components/ui'

interface RunbookListRowProps {
  runbook: RunbookSummary
  onSelect: (runbook: RunbookSummary) => void
  onDelete: (id: string) => void
}

export function RunbookListRow({ runbook, onSelect, onDelete }: RunbookListRowProps) {
  return (
    <div className="group flex flex-col items-start justify-between gap-3 px-5 py-5 transition-colors duration-100 hover:bg-neutral-50/80 sm:flex-row sm:items-center sm:gap-4 sm:px-6">
      <button
        type="button"
        onClick={() => onSelect(runbook)}
        className="flex min-w-0 w-full flex-1 cursor-pointer items-start gap-4 text-left focus-visible:outline-none"
      >
        <span className="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-xl border border-neutral-200/80 bg-neutral-50/80 text-neutral-700 transition-colors group-hover:bg-white">
          <NavRunbooksIcon className="size-5" />
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2.5">
            <p className="text-[15.5px] font-semibold text-neutral-900 group-hover:text-neutral-950">
              {runbook.title}
            </p>
            {runbook.service && (
              <span className="inline-flex items-center rounded-full bg-neutral-100 px-3 py-0.5 text-[12.5px] font-medium text-neutral-600">
                {runbook.service}
              </span>
            )}
          </div>

          {runbook.description ? (
            <p className="mt-1 line-clamp-1 text-[14px] text-neutral-500">
              {runbook.description}
            </p>
          ) : (
            <p className="mt-1 text-[13.5px] text-neutral-400">
              Added <TimeAgo date={runbook.created_at} />
            </p>
          )}
        </div>
      </button>

      <div className="flex w-full shrink-0 items-center justify-end gap-3 sm:w-auto">
        <span className="text-[13px] text-neutral-400">
          <TimeAgo date={runbook.created_at} />
        </span>

        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button
              variant="ghost"
              size="icon-sm"
              className="rounded-full text-neutral-400 opacity-0 transition-opacity group-hover:opacity-100 hover:bg-red-50 hover:text-red-600"
              title="Delete runbook"
            >
              <Trash2 className="size-4" />
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete &ldquo;{runbook.title}&rdquo;?</AlertDialogTitle>
              <AlertDialogDescription>
                This runbook will be permanently removed. The agent will no longer reference it
                during automated incident remediation.
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

        <button
          type="button"
          onClick={() => onSelect(runbook)}
          className="flex cursor-pointer items-center text-neutral-300 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-neutral-600"
          aria-label="Open runbook details"
        >
          <ChevronRight className="size-4" />
        </button>
      </div>
    </div>
  )
}
