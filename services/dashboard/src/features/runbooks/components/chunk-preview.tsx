import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import type { ChunkResult } from '../lib/chunker'

interface ChunkPreviewProps {
  chunkResult: ChunkResult
  onUpdateHeading?: (index: number, newHeading: string) => void
}

export function ChunkPreview({ chunkResult, onUpdateHeading }: ChunkPreviewProps) {
  const { sections, diagnostics } = chunkResult
  const [expandedSections, setExpandedSections] = useState<Record<number, boolean>>({
    0: true,
  })

  const toggleSection = (index: number) => {
    setExpandedSections((prev) => ({
      ...prev,
      [index]: !prev[index],
    }))
  }

  const toggleAll = () => {
    const allExpanded = sections.every((_, i) => expandedSections[i])
    const next: Record<number, boolean> = {}
    if (!allExpanded) {
      sections.forEach((_, i) => {
        next[i] = true
      })
    }
    setExpandedSections(next)
  }

  const isReady =
    diagnostics.hasTitle &&
    sections.length > 0 &&
    diagnostics.emptySections.length === 0

  return (
    <div className="flex flex-col gap-4">
      {/* Telemetry & Validation Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-neutral-200/80 bg-white px-5 py-3.5">
        <div className="flex flex-wrap items-center gap-3 text-[13.5px] text-neutral-500 tabular-nums">
          <span>
            <strong className="font-semibold text-neutral-900">{diagnostics.totalSections}</strong>{' '}
            {diagnostics.totalSections === 1 ? 'section' : 'sections'}
          </span>
          <span className="text-neutral-300">·</span>
          <span>{diagnostics.totalChars.toLocaleString()} chars</span>
          <span className="text-neutral-300">·</span>
          <span>~{diagnostics.estimatedTokens.toLocaleString()} tokens</span>
        </div>

        <div className="flex items-center gap-3">
          {isReady ? (
            <span className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-[12.5px] font-medium text-emerald-800 ring-1 ring-emerald-200/70">
              <span className="size-2 rounded-full bg-emerald-500" />
              Ready
            </span>
          ) : (
            <span className="inline-flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1 text-[12.5px] font-medium text-amber-800 ring-1 ring-amber-200/70">
              <span className="size-2 rounded-full bg-amber-500" />
              {!diagnostics.hasTitle ? 'Missing title' : 'Empty section'}
            </span>
          )}

          {sections.length > 0 && (
            <button
              type="button"
              onClick={toggleAll}
              className="cursor-pointer text-[13px] font-medium text-neutral-500 transition-colors hover:text-neutral-900"
            >
              {sections.every((_, i) => expandedSections[i]) ? 'Collapse all' : 'Expand all'}
            </button>
          )}
        </div>
      </div>

      {/* Empty section warning */}
      {diagnostics.emptySections.length > 0 && (
        <div className="rounded-2xl border border-amber-200/80 bg-amber-50/50 px-5 py-3.5 text-[13.5px] text-amber-900">
          Headings without body content: {diagnostics.emptySections.join(', ')}.
        </div>
      )}

      {/* Chunk list */}
      {sections.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-neutral-200 bg-neutral-50/40 px-6 py-14 text-center">
          <p className="text-[15px] font-medium text-neutral-700">No sections parsed</p>
          <p className="mt-1 text-[13.5px] text-neutral-400">
            Add Markdown headings (<code className="font-mono">## Step</code>) to partition the document.
          </p>
        </div>
      ) : (
        <div className="divide-y divide-neutral-100 overflow-hidden rounded-2xl border border-neutral-200/80 bg-white">
          {sections.map((section, idx) => {
            const isExpanded = Boolean(expandedSections[idx])
            return (
              <div key={`${section.order_index}-${idx}`}>
                <div
                  onClick={() => toggleSection(idx)}
                  className="flex cursor-pointer items-center justify-between gap-3 px-5 py-3.5 transition-colors hover:bg-neutral-50/80"
                >
                  <div className="flex min-w-0 flex-1 items-center gap-3.5">
                    <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-neutral-100 text-xs font-medium text-neutral-600 tabular-nums">
                      {section.order_index + 1}
                    </span>

                    <div className="min-w-0 flex-1">
                      {onUpdateHeading ? (
                        <input
                          type="text"
                          value={section.heading}
                          onClick={(e) => e.stopPropagation()}
                          onChange={(e) => onUpdateHeading(idx, e.target.value)}
                          className="w-full truncate border-b border-transparent bg-transparent text-[14.5px] font-medium text-neutral-900 transition-colors hover:border-neutral-300 focus:border-neutral-900 focus:outline-none"
                          placeholder="Section heading"
                        />
                      ) : (
                        <p className="truncate text-[14.5px] font-medium text-neutral-900">
                          {section.heading}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex shrink-0 items-center gap-3">
                    <span className="text-[12.5px] text-neutral-400 tabular-nums">
                      ~{section.tokenEstimate} tok
                    </span>
                    <ChevronRight
                      className={`size-4 text-neutral-400 transition-transform duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] ${
                        isExpanded ? 'rotate-90' : ''
                      }`}
                    />
                  </div>
                </div>

                <div
                  className={`grid transition-[grid-template-rows,opacity] duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] ${
                    isExpanded ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
                  }`}
                >
                  <div className="overflow-hidden">
                    <div className="border-t border-neutral-100 bg-neutral-50/40 px-5 py-4">
                      {section.content.trim() ? (
                        <pre className="max-h-60 overflow-x-auto rounded-xl border border-neutral-200/70 bg-white p-4 font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap text-neutral-800">
                          {section.content}
                        </pre>
                      ) : (
                        <p className="text-[13px] text-neutral-400">
                          Empty section content.
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
