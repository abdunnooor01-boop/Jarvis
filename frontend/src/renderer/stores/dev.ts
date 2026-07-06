import { create } from 'zustand'
import { useAuthStore } from './auth'

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy'
  timestamp: number
  uptime_seconds: number
  services: {
    database: {
      status: string
      type?: string
      error?: string
    }
    api: {
      status: string
    }
  }
}

export interface SystemMetrics {
  uptime_seconds: number
  users: { total: number }
  conversations: { total: number }
  messages: { total: number }
  task_plans: { total: number }
  audit_log_entries: { total: number }
  plugins: { total: number }
}

export interface SystemInfo {
  application: {
    name: string
    version: string
    environment: string
    debug: boolean
  }
  runtime: {
    python_version: string
    platform: string
    hostname: string
  }
  configuration: {
    app_name: string
    app_version: string
    environment: string
    debug: boolean
    llm_model: string
    cors_origins: string[]
    rate_limit_chat: number
    rate_limit_api: number
    database_type: string
    api_keys_configured: {
      openai: boolean
      anthropic: boolean
      gemini: boolean
      tavily: boolean
    }
  }
}

export interface DevTool {
  name: string
  description: string
  parameters: Record<string, any>
}

export interface AuditLogItem {
  id: number
  event_type: string
  actor_id: number | null
  actor_ip: string | null
  resource: string
  action: string
  status: string
  details: Record<string, any>
  created_at: string
}

export interface LogsResponse {
  items: AuditLogItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

interface DevState {
  health: HealthStatus | null
  metrics: SystemMetrics | null
  systemInfo: SystemInfo | null
  tools: DevTool[]
  logs: LogsResponse | null

  // Loading states
  healthLoading: boolean
  metricsLoading: boolean
  systemInfoLoading: boolean
  toolsLoading: boolean
  logsLoading: boolean

  error: string | null

  fetchHealth: () => Promise<void>
  fetchMetrics: () => Promise<void>
  fetchSystemInfo: () => Promise<void>
  fetchTools: () => Promise<void>
  fetchLogs: (filters?: { level?: string; search?: string; page?: number; page_size?: number }) => Promise<void>
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const useDevStore = create<DevState>((set, get) => ({
  health: null,
  metrics: null,
  systemInfo: null,
  tools: [],
  logs: null,

  healthLoading: false,
  metricsLoading: false,
  systemInfoLoading: false,
  toolsLoading: false,
  logsLoading: false,

  error: null,

  fetchHealth: async () => {
    set({ healthLoading: true, error: null })
    try {
      const token = useAuthStore.getState().token
      const response = await fetch(`${API_URL}/api/v1/dev/health`, {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch system health')
      }

      const data = await response.json()
      set({ health: data, healthLoading: false })
    } catch (err: any) {
      set({ error: err.message || 'Failed to fetch health status', healthLoading: false })
    }
  },

  fetchMetrics: async () => {
    set({ metricsLoading: true, error: null })
    try {
      const token = useAuthStore.getState().token
      const response = await fetch(`${API_URL}/api/v1/dev/metrics`, {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch system metrics')
      }

      const data = await response.json()
      set({ metrics: data, metricsLoading: false })
    } catch (err: any) {
      set({ error: err.message || 'Failed to fetch metrics', metricsLoading: false })
    }
  },

  fetchSystemInfo: async () => {
    set({ systemInfoLoading: true, error: null })
    try {
      const token = useAuthStore.getState().token
      const response = await fetch(`${API_URL}/api/v1/dev/system-info`, {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch system info')
      }

      const data = await response.json()
      set({ systemInfo: data, systemInfoLoading: false })
    } catch (err: any) {
      set({ error: err.message || 'Failed to fetch system info', systemInfoLoading: false })
    }
  },

  fetchTools: async () => {
    set({ toolsLoading: true, error: null })
    try {
      const token = useAuthStore.getState().token
      const response = await fetch(`${API_URL}/api/v1/dev/tools`, {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch tools introspection')
      }

      const data = await response.json()
      set({ tools: data.tools || [], toolsLoading: false })
    } catch (err: any) {
      set({ error: err.message || 'Failed to fetch tools', toolsLoading: false })
    }
  },

  fetchLogs: async (filters = {}) => {
    set({ logsLoading: true, error: null })
    try {
      const token = useAuthStore.getState().token
      const { level, search, page = 1, page_size = 20 } = filters

      // Construct query parameters
      const params = new URLSearchParams()
      if (level) params.append('level', level)
      if (search) params.append('search', search)
      params.append('page', page.toString())
      params.append('page_size', page_size.toString())

      const response = await fetch(`${API_URL}/api/v1/dev/logs?${params.toString()}`, {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch system logs')
      }

      const data = await response.json()
      set({ logs: data, logsLoading: false })
    } catch (err: any) {
      set({ error: err.message || 'Failed to fetch logs', logsLoading: false })
    }
  }
}))
