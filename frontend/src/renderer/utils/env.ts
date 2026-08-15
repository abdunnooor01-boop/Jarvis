export function getApiUrl(): string {
  // @ts-ignore
  if (window.api && typeof window.api.getBackendUrlSync === 'function') {
    // @ts-ignore
    const url = window.api.getBackendUrlSync()
    if (url) return url
  }
  // Web build (no Electron preload): resolve API calls against the page
  // origin — the :3000 web server proxies /api and /ws to the backend.
  // A relative base ('') makes fetch('' + '/api/v1/...') hit the same origin,
  // which is the only host a real user's browser can reach. NEVER fall back to
  // http://localhost:8000 here — that points at the USER's own machine.
  return import.meta.env.VITE_API_URL || ''
}
