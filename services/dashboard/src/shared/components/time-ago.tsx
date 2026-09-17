import { useNow } from '../hooks/use-now'

const MINUTE = 60
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

const DIVISIONS: Array<{ amount: number; unit: string }> = [
  { amount: DAY, unit: 'd' },
  { amount: HOUR, unit: 'h' },
  { amount: MINUTE, unit: 'm' },
  { amount: 1, unit: 's' },
]

function formatRelative(date: Date, now: Date): string {
  const diffSeconds = Math.round((now.getTime() - date.getTime()) / 1000)
  if (diffSeconds < 5) return 'just now'

  for (const { amount, unit } of DIVISIONS) {
    if (diffSeconds >= amount) {
      return `${Math.floor(diffSeconds / amount)}${unit} ago`
    }
  }
  return 'just now'
}

export function TimeAgo({ date }: { date: string }) {
  const now = useNow()
  return <span>{formatRelative(new Date(date), now)}</span>
}
