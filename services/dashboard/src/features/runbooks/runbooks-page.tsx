import { useMemo, useState } from 'react'
import { Plus, RefreshCw, Search, X } from 'lucide-react'
import { toast } from 'sonner'

import { Button, Skeleton } from '@/components/ui'
import { useDeleteRunbook, useRunbooksList } from './hooks/use-runbooks'
import { RunbookListRow } from './components/runbook-list-card'
import { RunbookDetailSheet } from './components/runbook-detail-sheet'
import { RunbookUploader } from './components/runbook-uploader'

export function RunbooksPage() {
  const { data: runbooks, isPending, isError, refetch } = useRunbooksList()

  const [activeTab, setActiveTab] = useState<'library' | 'upload'>('library')
  const [selectedRunbookId, setSelectedRunbookId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedServiceFilter, setSelectedServiceFilter] = useState<string | 'ALL'>('ALL')

  const deleteMutation = useDeleteRunbook({
    onSuccess: () => {
      toast.success('Runbook deleted')
      setSelectedRunbookId(null)
      refetch()
    },
    onError: (err: any) => {
      toast.error('Failed to delete runbook', {
        description: err?.message || 'An error occurred while deleting.',
      })
    },
  })

  const { metrics, services, filteredRunbooks } = useMemo(() => {
    const list = runbooks ?? []
    const svcSet = new Set<string>()
    list.forEach((rb) => {
      if (rb.service) svcSet.add(rb.service)
    })

    const filtered = list.filter((rb) => {
      const matchSearch =
        searchQuery === '' ||
        rb.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (rb.service && rb.service.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (rb.description && rb.description.toLowerCase().includes(searchQuery.toLowerCase()))

      const matchService =
        selectedServiceFilter === 'ALL' || rb.service === selectedServiceFilter

      return matchSearch && matchService
    })

    return {
      metrics: {
        totalRunbooks: list.length,
        totalServices: svcSet.size,
      },
      services: Array.from(svcSet),
      filteredRunbooks: filtered,
    }
  }, [runbooks, searchQuery, selectedServiceFilter])

  return (
    <div className="flex flex-col gap-8">
      {/* Page Header */}
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[26px] font-semibold tracking-tight text-neutral-900">
            Runbooks
          </h1>
          <p className="mt-1.5 text-[15px] text-neutral-500">
            Operational playbooks partitioned into discrete sections for automated agent retrieval.
          </p>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setActiveTab('library')}
            className={`inline-flex cursor-pointer items-center gap-2 rounded-full px-4 py-2 text-[14px] transition-colors duration-100 ${
              activeTab === 'library'
                ? 'bg-neutral-900 font-medium text-white'
                : 'bg-neutral-100/80 font-normal text-neutral-600 hover:bg-neutral-200/70 hover:text-neutral-900'
            }`}
          >
            <span>Library</span>
            <span
              className={`text-[12.5px] tabular-nums ${
                activeTab === 'library' ? 'text-neutral-300' : 'text-neutral-400'
              }`}
            >
              {metrics.totalRunbooks}
            </span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('upload')}
            className={`inline-flex cursor-pointer items-center gap-1.5 rounded-full px-4 py-2 text-[14px] transition-colors duration-100 ${
              activeTab === 'upload'
                ? 'bg-neutral-900 font-medium text-white'
                : 'bg-neutral-100/80 font-normal text-neutral-600 hover:bg-neutral-200/70 hover:text-neutral-900'
            }`}
          >
            <Plus className="size-4" />
            <span>Upload</span>
          </button>
        </div>
      </header>

      {/* View 1: Library Tab */}
      {activeTab === 'library' && (
        <div className="flex flex-col gap-6">
          {/* Search & Service Filter Bar */}
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => setSelectedServiceFilter('ALL')}
                className={`cursor-pointer rounded-full px-4 py-2 text-[14px] transition-colors duration-100 ${
                  selectedServiceFilter === 'ALL'
                    ? 'bg-neutral-900 font-medium text-white'
                    : 'bg-neutral-100/80 font-normal text-neutral-600 hover:bg-neutral-200/70 hover:text-neutral-900'
                }`}
              >
                All services
              </button>
              {services.map((svc) => (
                <button
                  key={svc}
                  type="button"
                  onClick={() => setSelectedServiceFilter(svc)}
                  className={`cursor-pointer rounded-full px-4 py-2 text-[14px] transition-colors duration-100 ${
                    selectedServiceFilter === svc
                      ? 'bg-neutral-900 font-medium text-white'
                      : 'bg-neutral-100/80 font-normal text-neutral-600 hover:bg-neutral-200/70 hover:text-neutral-900'
                  }`}
                >
                  {svc}
                </button>
              ))}
            </div>

            <div className="relative w-full sm:w-80">
              <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-neutral-400" />
              <input
                type="text"
                placeholder="Search runbooks…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-10 w-full rounded-full border border-neutral-200/90 bg-white pr-9 pl-10 text-[14px] text-neutral-900 placeholder:text-neutral-400 transition-colors focus:border-neutral-400 focus:outline-none"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer text-neutral-400 hover:text-neutral-700"
                >
                  <X className="size-4" />
                </button>
              )}
            </div>
          </div>

          {/* Loading State */}
          {isPending && (
            <div className="divide-y divide-neutral-100 overflow-hidden rounded-2xl border border-neutral-200/80 bg-white">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="flex items-center gap-4 px-6 py-5">
                  <Skeleton className="size-10 rounded-xl" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-1/3" />
                    <Skeleton className="h-3.5 w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Error State */}
          {isError && (
            <div className="flex items-center justify-between rounded-2xl border border-red-200/80 bg-red-50/50 px-6 py-4 text-[14px] text-red-700">
              <span>Unable to fetch runbooks from the backend service.</span>
              <Button
                variant="outline"
                size="sm"
                className="rounded-full bg-white"
                onClick={() => refetch()}
              >
                <RefreshCw className="mr-1.5 size-3.5" /> Retry
              </Button>
            </div>
          )}

          {/* Empty State */}
          {!isPending && !isError && filteredRunbooks.length === 0 && (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-neutral-200 bg-neutral-50/40 px-6 py-16 text-center">
              <p className="text-[15px] font-medium text-neutral-800">
                {searchQuery || selectedServiceFilter !== 'ALL'
                  ? 'No matching runbooks'
                  : 'No runbooks uploaded yet'}
              </p>
              <p className="mt-1.5 max-w-md text-[14px] text-neutral-500">
                {searchQuery || selectedServiceFilter !== 'ALL'
                  ? 'Try clearing your search or service filter.'
                  : 'Upload Markdown playbooks so the agent can reference validated recovery steps during P1/P2 incidents.'}
              </p>
              <div className="mt-5 flex items-center gap-2.5">
                <button
                  type="button"
                  onClick={() => setActiveTab('upload')}
                  className="inline-flex cursor-pointer items-center gap-1.5 rounded-full bg-neutral-900 px-4 py-2 text-[13.5px] font-medium text-white hover:bg-neutral-800"
                >
                  <Plus className="size-4" />
                  Upload runbook
                </button>
              </div>
            </div>
          )}

          {/* Runbooks List */}
          {!isPending && !isError && filteredRunbooks.length > 0 && (
            <div className="divide-y divide-neutral-100 overflow-hidden rounded-2xl border border-neutral-200/80 bg-white">
              {filteredRunbooks.map((rb) => (
                <RunbookListRow
                  key={rb.id}
                  runbook={rb}
                  onSelect={(item) => setSelectedRunbookId(item.id)}
                  onDelete={(id) => deleteMutation.mutate(id)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* View 2: Upload & Chunker Tab */}
      {activeTab === 'upload' && (
        <RunbookUploader
          onUploaded={() => {
            setActiveTab('library')
            refetch()
          }}
        />
      )}

      {/* Detail Sheet */}
      <RunbookDetailSheet
        runbookId={selectedRunbookId}
        onClose={() => setSelectedRunbookId(null)}
        onDelete={(id) => deleteMutation.mutate(id)}
      />
    </div>
  )
}
