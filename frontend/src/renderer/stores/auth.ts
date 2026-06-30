import { create } from 'zustand'

interface AuthState {
  token: string | null
  user: {
    email: string
    displayName: string
  } | null
  isAuthenticated: boolean
  setAuth: (token: string, user: { email: string; displayName: string }) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  isAuthenticated: false,
  setAuth: async (token, user) => {
    // @ts-ignore
    await window.api.store.set('auth-token', token)
    // @ts-ignore
    await window.api.store.set('auth-user', user)
    set({ token, user, isAuthenticated: true })
  },
  logout: async () => {
    // @ts-ignore
    await window.api.store.delete('auth-token')
    // @ts-ignore
    await window.api.store.delete('auth-user')
    set({ token: null, user: null, isAuthenticated: false })
  }
}))
