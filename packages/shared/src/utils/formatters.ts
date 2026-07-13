/**
 * Formats a date string or Date object into a localized date string.
 */
export function formatDate(date: string | Date, options?: Intl.DateTimeFormatOptions): string {
  if (!date) return ''
  const d = typeof date === 'string' ? new Date(date) : date
  if (isNaN(d.getTime())) return ''
  return d.toLocaleDateString(undefined, options || { year: 'numeric', month: 'short', day: 'numeric' })
}

/**
 * Formats a date string or Date object into a localized time string.
 */
export function formatTime(date: string | Date): string {
  if (!date) return ''
  const d = typeof date === 'string' ? new Date(date) : date
  if (isNaN(d.getTime())) return ''
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
}

/**
 * Formats a date string or Date object into a localized date and time string.
 */
export function formatDateTime(date: string | Date): string {
  if (!date) return ''
  const d = typeof date === 'string' ? new Date(date) : date
  if (isNaN(d.getTime())) return ''
  return `${formatDate(d)} ${formatTime(d)}`
}

/**
 * Formats a duration in seconds to a human-readable string (e.g. "2m 15s" or "45s" or "1h 5m").
 */
export function formatDuration(seconds: number): string {
  if (seconds < 0) return '0s'
  const hrs = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60

  const parts = []
  if (hrs > 0) parts.push(`${hrs}h`)
  if (mins > 0) parts.push(`${mins}m`)
  if (secs > 0 || parts.length === 0) parts.push(`${secs}s`)

  return parts.join(' ')
}

/**
 * Formats a numeric price into USD formatting.
 */
export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(amount)
}
