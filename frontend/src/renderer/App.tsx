import React, { useState, useEffect } from 'react'
import { useAuthStore } from './stores/auth'
import { useSettingsStore } from './stores/settings'
import ChatWindow from './components/ChatWindow'
import Sidebar from './components/Sidebar'
import Login from './components/Login'
import Signup from './components/Signup'
import SettingsModal from './components/SettingsModal'
import MemoryIndicator from './components/MemoryIndicator'

const App: React.FC = () => {
  const { isAuthenticated, setAuth } = useAuthStore()
  const { loadSettings } = useSettingsStore()
  const [view, setView] = useState<'login' | 'signup'>('login')
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [isInitializing, setIsInitializing] = useState(true)

  useEffect(() => {
    const init = async () => {
      await loadSettings()
      // @ts-ignore
      const token = await window.api.store.get('auth-token')
      // @ts-ignore
      const user = await window.api.store.get('auth-user')
      if (token && user) {
        setAuth(token, user)
      }
      setIsInitializing(false)
    }
    init()
  }, [])

  if (isInitializing) {
    return (
      <div className="flex h-screen items-center justify-center bg-white dark:bg-slate-950">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
        {view === 'login' ? (
          <Login onSwitch={() => setView('signup')} />
        ) : (
          <Signup onSwitch={() => setView('login')} />
        )}
      </div>
    )
  }

  return (
    <div className="flex h-screen overflow-hidden bg-white dark:bg-slate-900">
      <Sidebar onOpenSettings={() => setIsSettingsOpen(true)} />
      <main className="flex-1 flex flex-col min-w-0 relative">
        <header className="h-14 flex items-center px-6 border-b border-slate-200 dark:border-slate-800 flex-shrink-0 draggable">
          <h1 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Jarvis</h1>
        </header>
        <MemoryIndicator />
        <ChatWindow />
      </main>
      {isSettingsOpen && <SettingsModal onClose={() => setIsSettingsOpen(false)} />}
    </div>
  )
}

export default App
