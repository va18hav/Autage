import { useMemo, useState } from 'react'
import { Upload } from 'lucide-react'
import { toast } from 'sonner'

import { Button, Input, Label } from '@/components/ui'
import {
  chunkRunbookMarkdown,
  toRunbookCreatePayload,
  type ChunkResult,
} from '../lib/chunker'
import { useCreateRunbook } from '../hooks/use-runbooks'
import { ChunkPreview } from './chunk-preview'

interface RunbookUploaderProps {
  onUploaded?: () => void
}

export function RunbookUploader({ onUploaded }: RunbookUploaderProps) {
  const [rawMarkdown, setRawMarkdown] = useState<string>('')
  const [titleOverride, setTitleOverride] = useState<string>('')
  const [serviceOverride, setServiceOverride] = useState<string>('')
  const [triggersInput, setTriggersInput] = useState<string>('')
  const [descriptionOverride, setDescriptionOverride] = useState<string>('')
  const [isDragOver, setIsDragOver] = useState(false)

  const chunkResult = useMemo<ChunkResult>(() => {
    const customTriggers = triggersInput
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)

    return chunkRunbookMarkdown(rawMarkdown, {
      title: titleOverride || undefined,
      service: serviceOverride || undefined,
      triggers: customTriggers.length > 0 ? customTriggers : undefined,
      description: descriptionOverride || undefined,
    })
  }, [rawMarkdown, titleOverride, serviceOverride, triggersInput, descriptionOverride])

  const resetUploadForm = () => {
    setRawMarkdown('')
    setTitleOverride('')
    setServiceOverride('')
    setTriggersInput('')
    setDescriptionOverride('')
  }

  const createMutation = useCreateRunbook({
    onSuccess: () => {
      toast.success('Runbook uploaded', {
        description: `"${chunkResult.title}" indexed with ${chunkResult.sections.length} sections.`,
      })
      resetUploadForm()
      onUploaded?.()
    },
    onError: (err: any) => {
      toast.error('Failed to upload runbook', {
        description: err?.message || 'Check network connection or API status.',
      })
    },
  })

  const handleFileUpload = (file: File) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      const content = e.target?.result
      if (typeof content === 'string') {
        setRawMarkdown(content)
        setTitleOverride('')
        setServiceOverride('')
        setTriggersInput('')
        setDescriptionOverride('')
        toast.success(`Loaded file: ${file.name}`)
      }
    }
    reader.readAsText(file)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) {
      handleFileUpload(file)
    }
  }

  const handleSaveRunbook = () => {
    if (!chunkResult.diagnostics.hasTitle) {
      toast.error('Title is required', {
        description: 'Please specify a runbook title before uploading.',
      })
      return
    }

    if (chunkResult.sections.length === 0) {
      toast.error('No sections found', {
        description: 'Runbook must have at least one section.',
      })
      return
    }

    const payload = toRunbookCreatePayload(chunkResult)
    createMutation.mutate(payload)
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Drag & Drop File Upload Bar */}
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragOver(true)
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        className={`flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-dashed px-6 py-5 transition-colors ${
          isDragOver
            ? 'border-neutral-900 bg-neutral-100/70'
            : 'border-neutral-300/90 bg-neutral-50/40 hover:border-neutral-400'
        }`}
      >
        <div>
          <p className="text-[14.5px] font-medium text-neutral-900">
            Drop a Markdown (<code className="font-mono text-[13px]">.md</code>) file here, or browse from your computer
          </p>
          <p className="mt-0.5 text-[13px] text-neutral-500">
            YAML frontmatter and headings (<code className="font-mono text-[12px]">#</code> / <code className="font-mono text-[12px]">##</code>) are automatically parsed into ordered sections.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="file"
            id="runbook-file-upload"
            accept=".md,.markdown,.txt"
            className="sr-only"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) handleFileUpload(file)
            }}
          />
          <label
            htmlFor="runbook-file-upload"
            className="inline-flex cursor-pointer items-center gap-2 rounded-full bg-neutral-900 px-4 py-2 text-[13.5px] font-medium text-white transition-colors hover:bg-neutral-800"
          >
            <Upload className="size-3.5" />
            <span>Choose .md file</span>
          </label>
        </div>
      </div>

      {/* Two-Column Workbench */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left Column: Metadata + Markdown Editor */}
        <div className="flex flex-col gap-5">
          <div className="overflow-hidden rounded-2xl border border-neutral-200/80 bg-white">
            <div className="border-b border-neutral-100 px-6 py-4">
              <h3 className="text-[15.5px] font-semibold text-neutral-900">
                Runbook Metadata
              </h3>
            </div>
            <div className="space-y-4 p-6">
              <div className="space-y-1.5">
                <Label htmlFor="runbook-title" className="text-[13.5px] text-neutral-700">
                  Title <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="runbook-title"
                  placeholder="e.g. PostgreSQL Connection Pool Exhaustion"
                  value={titleOverride || chunkResult.title}
                  onChange={(e) => setTitleOverride(e.target.value)}
                  className="h-10 rounded-xl bg-white text-[14px]"
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="runbook-service" className="text-[13.5px] text-neutral-700">
                    Service
                  </Label>
                  <Input
                    id="runbook-service"
                    placeholder="e.g. auth-service"
                    value={serviceOverride || chunkResult.service || ''}
                    onChange={(e) => setServiceOverride(e.target.value)}
                    className="h-10 rounded-xl bg-white font-mono text-[13px]"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="runbook-triggers" className="text-[13.5px] text-neutral-700">
                    Triggers (comma-separated)
                  </Label>
                  <Input
                    id="runbook-triggers"
                    placeholder="OOMKilled, PodRestart"
                    value={triggersInput || chunkResult.triggers.join(', ')}
                    onChange={(e) => setTriggersInput(e.target.value)}
                    className="h-10 rounded-xl bg-white font-mono text-[13px]"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="runbook-desc" className="text-[13.5px] text-neutral-700">
                  Summary
                </Label>
                <Input
                  id="runbook-desc"
                  placeholder="Short operational summary…"
                  value={descriptionOverride || chunkResult.description || ''}
                  onChange={(e) => setDescriptionOverride(e.target.value)}
                  className="h-10 rounded-xl bg-white text-[14px]"
                />
              </div>
            </div>
          </div>

          <div className="overflow-hidden rounded-2xl border border-neutral-200/80 bg-white">
            <div className="flex items-center justify-between border-b border-neutral-100 px-6 py-4">
              <h3 className="text-[15.5px] font-semibold text-neutral-900">
                Markdown Source
              </h3>
              <span className="text-[13px] text-neutral-400 tabular-nums">
                {rawMarkdown.length.toLocaleString()} chars
              </span>
            </div>
            <div className="p-4">
              <textarea
                rows={16}
                value={rawMarkdown}
                onChange={(e) => setRawMarkdown(e.target.value)}
                placeholder="Upload a .md file above or paste your Markdown runbook here..."
                className="w-full resize-y rounded-xl border border-neutral-200/80 bg-neutral-50/40 p-4 font-mono text-[13px] leading-relaxed text-neutral-900 focus:border-neutral-400 focus:bg-white focus:outline-none"
              />
            </div>
          </div>
        </div>

        {/* Right Column: Live Chunk Preview */}
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-[16px] font-semibold text-neutral-900">
                Parsed Sections
              </h3>
              <p className="text-[13.5px] text-neutral-500">
                Discrete chunks indexed for agent retrieval.
              </p>
            </div>

            <Button
              size="sm"
              className="rounded-full px-5"
              onClick={handleSaveRunbook}
              disabled={createMutation.isPending || !chunkResult.diagnostics.hasTitle}
            >
              {createMutation.isPending ? 'Uploading…' : 'Upload Runbook'}
            </Button>
          </div>

          <ChunkPreview chunkResult={chunkResult} />
        </div>
      </div>
    </div>
  )
}
