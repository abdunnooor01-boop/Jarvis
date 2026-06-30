import { create } from 'zustand'

type Theme = 'light' | 'dark' | 'system'

interface SettingsState {
  theme: Theme
  openAiKey: string
  setTheme: (theme: Theme) => void
  setOpenAiKey: (key: string) => void
  loadSettings: () => Promise<void>
}

export const useSettingsStore = create<SettingsState>((set) => ({
  theme: 'system',
  openAiKey: '',
  setTheme: async (theme) => {
    // @ts-ignore
    await window.api.store.set('settings-theme', theme)
    set({ theme })
    applyTheme(theme)
  },
  setOpenAiKey: async (key) => {
    // @ts-ignore
    await window.api.store.set('settings-openai-key', key)
    set({ openAiKey: key })
  },
  loadSettings: async () => {
    // @ts-ignore
    const theme = await window.api.store.get('settings-theme') || 'system'
    // @ts-ignore
    const openAiKey = await window.api.store.get('settings-openai-key') || ''
    set({ theme, openAiKey })
    applyTheme(theme)
  }
}))

function applyTheme(theme: Theme) {
  const root = window.document.documentElement
  let isDark = theme === 'dark'
  if (theme === 'system') {
    isDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  }

  if (isDark) {
    root.classList.add('dark')
  } else {
    root.classList.remove('dark')
  }
}
