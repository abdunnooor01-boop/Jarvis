import { create } from 'zustand'
import { useAuthStore } from './auth'

export interface Plugin {
  name: string
  version: string
  description: string
  author: string
  enabled: boolean
  installed_at: string
  tool_count: number
}

interface PluginState {
  plugins: Plugin[]
  isLoading: boolean
  error: string | null
  fetchPlugins: () => Promise<void>
  togglePlugin: (name: string) => Promise<void>
  installPlugin: (name: string) => Promise<void>
  uninstallPlugin: (name: string) => Promise<void>
}

import { getApiUrl } from '../utils/env'

const API_URL = getApiUrl()

export const usePluginStore = create<PluginState>((set, get) => ({
  plugins: [],
  isLoading: false,
  error: null,

  fetchPlugins: async () => {
    set({ isLoading: true, error: null })
    try {
      const token = useAuthStore.getState().token
      const response = await fetch(`${API_URL}/api/v1/plugins`, {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch plugins')
      }

      const data = await response.json()
      set({ plugins: data, isLoading: false })
    } catch (err: any) {
      set({ error: err.message || 'An error occurred', isLoading: false })
    }
  },

  togglePlugin: async (name: string) => {
    const previousPlugins = get().plugins
    set({
      plugins: previousPlugins.map((p) =>
        p.name === name ? { ...p, enabled: !p.enabled } : p
      )
    })

    try {
      const token = useAuthStore.getState().token
      const response = await fetch(`${API_URL}/api/v1/plugins/${name}/toggle`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('Failed to toggle plugin')
      }

      const updatedPlugin = await response.json()
      set({
        plugins: get().plugins.map((p) =>
          p.name === name ? { ...p, ...updatedPlugin } : p
        )
      })
    } catch (err: any) {
      set({
        plugins: previousPlugins,
        error: err.message || 'Failed to toggle plugin'
      })
    }
  },

  installPlugin: async (name: string) => {
    console.log('Installing plugin:', name)
  },

  uninstallPlugin: async (name: string) => {
    console.log('Uninstalling plugin:', name)
  }
}))
