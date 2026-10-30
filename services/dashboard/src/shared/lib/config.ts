const rawApiUrl = import.meta.env.VITE_API_URL as string | undefined

export const API_URL = (
  rawApiUrl && rawApiUrl.trim().length > 0
    ? rawApiUrl.trim()
    : typeof window !== 'undefined'
      ? window.location.origin
      : ''
).replace(/\/$/, '')

const webhookPath = `${API_URL}/webhooks/alert`
export const WEBHOOK_ALERT_URL =
  typeof window !== 'undefined'
    ? new URL(webhookPath, window.location.origin).toString()
    : webhookPath
