const rawApiUrl = import.meta.env.VITE_API_URL as string | undefined

export const API_URL = (
  rawApiUrl && rawApiUrl.trim().length > 0
    ? rawApiUrl.trim()
    : typeof window !== 'undefined'
      ? window.location.origin
      : ''
).replace(/\/$/, '')

export const WEBHOOK_ALERT_URL = `${API_URL}/webhooks/alert`
