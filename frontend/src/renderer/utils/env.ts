export function getApiUrl(): string {
  // @ts-ignore
  if (window.api && typeof window.api.getBackendUrlSync === 'function') {
    // @ts-ignore
    const url = window.api.getBackendUrlSync()
    if (url) return url
  }
  return import.meta.env.VITE_API_URL || 'http://localhost:8000'
}
