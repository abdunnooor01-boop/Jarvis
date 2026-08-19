import React, { useState, useEffect } from 'react'
import { useAuthStore } from './stores/auth'
import { useSettingsStore } from './stores/settings'
import { useChatStore } from './stores/chat'
import { useTaskStore } from './stores/tasks'
import { getMe, ApiError, fetchConversations } from './utils/api'
import ChatWindow from './components/ChatWindow'
import Sidebar from './components/Sidebar'
import Login from './components/Login'
import Signup from './components/Signup'
import SettingsModal from './components/SettingsModal'
import MemoryIndicator from './components/MemoryIndicator'
import PluginManager from './components/PluginManager'
import { TaskPlanPanel } from './components/TaskPlanPanel'
import { TaskHistory } from './components/TaskHistory'
import { DevConsole } from './components/DevConsole'
import { FreelancerDashboard } from './components/FreelancerDashboard'
import { KnowledgeFeed } from './components/KnowledgeFeed'
import { TestingDashboard } from './components/TestingDashboard'

const App: React.FC = () => {
  const { isAuthenticated, setAuth, logout } = useAuthStore()
  const { loadSettings } = useSettingsStore()
  const { setConversations, setCurrentConversation } = useChatStore()
  const activePlan = useTaskStore((s) => s.activePlan)
  const [view, setView] = useState<'login' | 'signup'>('login')
  const [isInitializing, setIsInitializing] = useState(true)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [isPluginsOpen, setIsPluginsOpen] = useState(false)
  const [isTasksOpen, setIsTasksOpen] = useState(false)
  const [isDevConsoleOpen, setIsDevConsoleOpen] = useState(false)
  const [isFreelanceOpen, setIsFreelanceOpen] = useState(false)
  const [isKnowledgeOpen, setIsKnowledgeOpen] = useState(false)
  const [isTestingOpen, setIsTestingOpen] = useState(false)

  useEffect(() => {
    const init = async () => {
      await loadSettings()
      // @ts-ignore
      const token = await window.api.store.get('auth-token')
      // @ts-ignore
      const user = await window.api.store.get('auth-user')
      if (token && user) {
        try {
          // Validate the stored token against the backend — a stale/fake
          // token (e.g. an old 'mock-token') must not be reused, or the
          // WebSocket auth will fail forever and chat will never load.
          const me = await getMe(token)
          setAuth(token, { email: me.email, displayName: me.display_name })
          // Load existing conversations so history persists across refreshes.
          try {
            const convs = await fetchConversations(token)
            if (convs.length > 0) {
              setConversations(convs.map((c) => ({ id: c.id, title: c.title })))
              setCurrentConversation(convs[0].id)
            }
          } catch {
            // Conversation load is non-fatal — chat still works from scratch.
          }
        } catch (err) {
          if (err instanceof ApiError && err.status === 401) {
            // Token invalid/expired — clear it and show the login screen
            await logout()
          }
          // Other errors (e.g. backend unreachable): keep the stored token
          // and let the app try; the WS layer will surface connectivity issues.
          else {
            setAuth(token, user)
          }
        }
      }
      setIsInitializing(false)
    }
    init()
  }, [])

  if (isInitializing) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950">
        {view === 'login' ? (
          <Login onSwitch={() => setView('signup')} />
        ) : (
          <Signup onSwitch={() => setView('login')} />
        )}
      </div>
    )
  }

  const startNewChat = () => setCurrentConversation(null)

  return (
    <div className="flex h-screen overflow-hidden bg-slate-950">
      <Sidebar
        onNewChat={startNewChat}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenPlugins={() => setIsPluginsOpen(true)}
        onOpenTasks={() => setIsTasksOpen(true)}
        onOpenDevConsole={() => setIsDevConsoleOpen(true)}
        onOpenFreelance={() => setIsFreelanceOpen(true)}
        onOpenKnowledge={() => setIsKnowledgeOpen(true)}
        onOpenTesting={() => setIsTestingOpen(true)}
      />
      <main className="flex-1 flex min-w-0 relative">
        <div className="flex-1 flex flex-col min-w-0">
          <header className="h-14 flex items-center justify-center px-6 border-b border-slate-800 flex-shrink-0">
            <h1 className="text-sm font-semibold text-slate-300 tracking-widest uppercase">Jarvis</h1>
          </header>
          <MemoryIndicator />
          <ChatWindow />
        </div>
        {activePlan && <TaskPlanPanel />}
      </main>
      {isSettingsOpen && (
        <SettingsModal onClose={() => setIsSettingsOpen(false)} onOpenPlugins={() => setIsPluginsOpen(true)} />
      )}
      {isPluginsOpen && <PluginManager onClose={() => setIsPluginsOpen(false)} />}
      {isTasksOpen && <TaskHistory onClose={() => setIsTasksOpen(false)} />}
      {isDevConsoleOpen && <DevConsole onClose={() => setIsDevConsoleOpen(false)} />}
      {isFreelanceOpen && <FreelancerDashboard onClose={() => setIsFreelanceOpen(false)} />}
      {isKnowledgeOpen && <KnowledgeFeed onClose={() => setIsKnowledgeOpen(false)} />}
      {isTestingOpen && <TestingDashboard onClose={() => setIsTestingOpen(false)} />}
    </div>
  )
}

export default App