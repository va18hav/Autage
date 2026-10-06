import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { StatusBadge } from '../../../shared/components/status-badge'
import type { IncidentStatus } from '../../../shared/types/incident'

export function LiveHeader({ title, status }: { title: string; status: IncidentStatus }) {
  const isLive = status === 'PENDING' || status === 'TRIAGING'

  return (
    <header className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <Button asChild variant="outline" size="icon" className="size-9">
          <Link to="/dashboard" aria-label="Back to dashboard">
            <ArrowLeft className="size-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
          <p className="mt-0.5 text-xs text-muted-foreground">Live incident view</p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {isLive && (
          <Badge variant="outline" className="gap-1.5 border-red-200/80 bg-red-50 text-red-600">
            <span className="relative flex size-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-500 opacity-75" />
              <span className="relative inline-flex size-2 rounded-full bg-red-500" />
            </span>
            Live
          </Badge>
        )}
        <StatusBadge status={status} />
      </div>
    </header>
  )
}
