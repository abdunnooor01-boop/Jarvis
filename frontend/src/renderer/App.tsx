import React, { useState, useEffect } from 'react'
import { useAuthStore } from './stores/auth'
import { useSettingsStore } from './stores/settings'
import { useTaskStore } from './stores/tasks'
import ChatWindow from './components/ChatWindow'
import Sidebar from './components/Sidebar'
import Login from './components/Login'
import Signup from './components/Signup'
import SettingsModal from './components/SettingsModal'
import MemoryIndicator from './components/MemoryIndicator'
import PluginManager from './components/PluginManager'
import { TaskPlanPanel } from './components/TaskPlanPanel'
import { TaskHistory } from './components/TaskHistory'

const App: React.FC = () => {
  const { isAuthenticated, setAuth } = useAuthStore()
  const { loadSettings } = useSettingsStore()
  const { activePlan } = useTaskStore()
  const [view, setView] = useState<'login' | 'signup'>('login')
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [isPluginsOpen, setIsPluginsOpen] = useState(false)
  const [isTasksOpen, setIsTasksOpen] = useState(false)
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
      <Sidebar
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenPlugins={() => setIsPluginsOpen(true)}
        onOpenTasks={() => setIsTasksOpen(true)}
      />
      <main className="flex-1 flex min-w-0 relative">
        <div className="flex-1 flex flex-col min-w-0 border-r border-slate-200 dark:border-slate-800">
          <header className="h-14 flex items-center px-6 border-b border-slate-200 dark:border-slate-800 flex-shrink-0 draggable">
            <h1 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Jarvis</h1>
          </header>
          <MemoryIndicator />
          <ChatWindow />
        </div>
        {activePlan && <TaskPlanPanel />}
      </main>
      {isSettingsOpen && <SettingsModal onClose={() => setIsSettingsOpen(false)} onOpenPlugins={() => setIsPluginsOpen(true)} />}
      {isPluginsOpen && <PluginManager onClose={() => setIsPluginsOpen(false)} />}
      {isTasksOpen && <TaskHistory onClose={() => setIsTasksOpen(false)} />}
    </div>
  )
}

export default App
