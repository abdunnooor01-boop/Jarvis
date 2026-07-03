import { create } from 'zustand'

export interface Memory {
  id: string
  content: string
  timestamp: string
}

interface MemoryState {
  isEnabled: boolean
  isRecalling: boolean
  memories: Memory[]
  recentContext: string
  toggleMemory: () => void
  setRecalling: (isRecalling: boolean) => void
  addMemoryContext: (context: string) => void
  clearRecentContext: () => void
  clearAllMemories: () => void
}

const getStoredIsEnabled = (): boolean => {
  const stored = localStorage.getItem('jarvis-memory-enabled')
  return stored !== null ? stored === 'true' : true
}

export const useMemoryStore = create<MemoryState>((set) => ({
  isEnabled: getStoredIsEnabled(),
  isRecalling: false,
  memories: [],
  recentContext: '',
  
  toggleMemory: () => set((state) => {
    const nextEnabled = !state.isEnabled
    localStorage.setItem('jarvis-memory-enabled', String(nextEnabled))
    return { isEnabled: nextEnabled }
  }),
  
  setRecalling: (isRecalling) => set({ isRecalling }),
  
  addMemoryContext: (context) => set((state) => {
    const newMemory: Memory = {
      id: Date.now().toString() + Math.random().toString(36).substring(2, 5),
      content: context,
      timestamp: new Date().toISOString()
    }
    return {
      recentContext: context,
      memories: [newMemory, ...state.memories].slice(0, 50)
    }
  }),
  
  clearRecentContext: () => set({ recentContext: '' }),
  clearAllMemories: () => set({ memories: [], recentContext: '' })
}))
