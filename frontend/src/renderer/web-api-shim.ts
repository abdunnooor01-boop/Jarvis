/**
 * Web API shim — provides Electron IPC shims for browser-only builds.
 * When running in a browser (via vite.web.config.ts), `window.api` 
 * doesn't exist because it's normally exposed by the Electron preload script.
 * This shim provides the same interface using localStorage.
 */

interface StoreShim {
  get: (key: string) => Promise<any>
  set: (key: string, value: any) => Promise<void>
  delete: (key: string) => Promise<void>
}

interface ApiShim {
  store: StoreShim
  getBackendUrlSync: () => string
  getBackendUrl: () => Promise<string>
  setBackendUrl: (url: string) => Promise<void>
  // Web (hosted) builds have no local host, so the local executor is never
  // available here — the backend already blocks these tools in hosted mode.
  localExecutor?: any
}

// Only install the shim if window.api doesn't exist (i.e., not in Electron)
if (typeof window !== 'undefined' && !(window as any).api) {
  const store: StoreShim = {
    get: async (key: string) => {
      try {
        const value = localStorage.getItem(`jarvis:${key}`)
        return value ? JSON.parse(value) : null
      } catch {
        return null
      }
    },
    set: async (key: string, value: any) => {
      try {
        localStorage.setItem(`jarvis:${key}`, JSON.stringify(value))
      } catch (e) {
        console.warn('Failed to save to localStorage', key, e)
      }
    },
    delete: async (key: string) => {
      try {
        localStorage.removeItem(`jarvis:${key}`)
      } catch (e) {
        console.warn('Failed to remove from localStorage', key, e)
      }
    }
  }

  const api: ApiShim = {
    store,
    getBackendUrlSync: () => {
      return localStorage.getItem('jarvis:backend-url') || 'http://localhost:8000'
    },
    getBackendUrl: async () => {
      return localStorage.getItem('jarvis:backend-url') || 'http://localhost:8000'
    },
    setBackendUrl: async (url: string) => {
      localStorage.setItem('jarvis:backend-url', url)
    }
  }

  ;(window as any).api = api
}