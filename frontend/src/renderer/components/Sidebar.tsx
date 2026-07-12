import React from 'react'
import { Plus, MessageSquare, Settings, LogOut, User, Puzzle, History, Terminal, DollarSign, BookOpen } from 'lucide-react'
import { useChatStore } from '../stores/chat'
import { useAuthStore } from '../stores/auth'

interface SidebarProps {
  onOpenSettings: () => void
  onOpenPlugins: () => void
  onOpenTasks: () => void
  onOpenDevConsole: () => void
  onOpenFreelance: () => void
  onOpenKnowledge: () => void
}

const Sidebar: React.FC<SidebarProps> = ({ onOpenSettings, onOpenPlugins, onOpenTasks, onOpenDevConsole, onOpenFreelance, onOpenKnowledge }) => {
  const { conversations, currentConversationId, setCurrentConversation } = useChatStore()
  const { user, logout } = useAuthStore()

  return (
    <aside className="w-64 bg-slate-50 dark:bg-slate-950 border-r border-slate-200 dark:border-slate-800 flex flex-col flex-shrink-0">
      <div className="p-4">
        <button
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors"
          onClick={() => {/* TODO: New chat */}}
        >
          <Plus size={16} />
          New Conversation
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 space-y-1">
        {conversations.map((conv) => (
          <button
            key={conv.id}
            onClick={() => setCurrentConversation(conv.id)}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
              currentConversationId === conv.id
                ? 'bg-slate-200 dark:bg-slate-800 text-slate-900 dark:text-white'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-900'
            }`}
          >
            <MessageSquare size={16} />
            <span className="truncate">{conv.title}</span>
          </button>
        ))}
        {conversations.length === 0 && (
          <div className="px-3 py-10 text-center text-xs text-slate-400">
            No history yet
          </div>
        )}
      </div>

      <div className="p-4 border-t border-slate-200 dark:border-slate-800 space-y-1">
        <div className="flex items-center gap-3 px-3 py-2 text-sm text-slate-700 dark:text-slate-300">
          <div className="w-8 h-8 rounded-full bg-indigo-100 dark:bg-indigo-900 flex items-center justify-center text-indigo-700 dark:text-indigo-300">
            <User size={16} />
          </div>
          <span className="truncate font-medium">{user?.displayName || 'User'}</span>
        </div>
        <button
          onClick={onOpenPlugins}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
        >
          <Puzzle size={16} />
          Plugins
        </button>
        <button
          onClick={onOpenTasks}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
        >
          <History size={16} />
          Tasks
        </button>
        <button
          onClick={onOpenFreelance}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
        >
          <DollarSign size={16} />
          Freelance
        </button>
        <button
          onClick={onOpenKnowledge}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
        >
          <BookOpen size={16} />
          Knowledge
        </button>
        <button
          onClick={onOpenDevConsole}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
        >
          <Terminal size={16} />
          Developer
        </button>
        <button
          onClick={onOpenSettings}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
        >
          <Settings size={16} />
          Settings
        </button>
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
        >
          <LogOut size={16} />
          Logout
        </button>
      </div>
    </aside>
  )
}

export default Sidebar
