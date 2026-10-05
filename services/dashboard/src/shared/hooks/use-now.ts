import { useEffect, useState } from 'react'

const REFRESH_INTERVAL_MS = 30_000

export function useNow(intervalMs = REFRESH_INTERVAL_MS): Date {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), intervalMs)
    return () => clearInterval(timer)
  }, [intervalMs])

  return now
}
