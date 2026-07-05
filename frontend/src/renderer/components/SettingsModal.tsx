import React, { useState } from 'react'
import { X, Moon, Sun, Monitor, Brain, Trash2, Puzzle } from 'lucide-react'
import { useSettingsStore } from '../stores/settings'
import { useMemoryStore } from '../stores/memory'
import { usePluginStore } from '../stores/plugins'

interface SettingsModalProps {
  onClose: () => void
  onOpenPlugins: () => void
}

const SettingsModal: React.FC<SettingsModalProps> = ({ onClose, onOpenPlugins }) => {
  const { theme, setTheme, openAiKey, setOpenAiKey } = useSettingsStore()
  const { isEnabled, toggleMemory, clearAllMemories, memories } = useMemoryStore()
  const { plugins } = usePluginStore()
  const [isConfirmingClear, setIsConfirmingClear] = useState(false)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-2xl shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800">
          <h3 className="font-bold text-slate-900 dark:text-white">Settings</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
            <X size={20} />
          </button>
        </div>

        <div className="p-6 space-y-8">
          <section>
            <label className="block text-xs font-semibold text-slate-500 uppercase mb-4">Appearance</label>
            <div className="grid grid-cols-3 gap-3">
              {[
                { id: 'light', icon: Sun, label: 'Light' },
                { id: 'dark', icon: Moon, label: 'Dark' },
                { id: 'system', icon: Monitor, label: 'System' }
              ].map((item) => (
                <button
                  key={item.id}
                  onClick={() => setTheme(item.id as any)}
                  className={`flex flex-col items-center gap-2 p-3 rounded-xl border-2 transition-all ${
                    theme === item.id
                      ? 'border-indigo-600 bg-indigo-50 dark:bg-indigo-950/30'
                      : 'border-transparent bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700'
                  }`}
                >
                  <item.icon size={20} className={theme === item.id ? 'text-indigo-600' : 'text-slate-500'} />
                  <span className={`text-xs font-medium ${theme === item.id ? 'text-indigo-600' : 'text-slate-500'}`}>
                    {item.label}
                  </span>
                </button>
              ))}
            </div>
          </section>

          <section>
            <label className="block text-xs font-semibold text-slate-500 uppercase mb-2">API Configuration</label>
            <p className="text-xs text-slate-400 mb-4">Your API keys are stored locally and never leave your machine.</p>
            <div className="space-y-4">
              <div>
                <label className="block text-[10px] font-bold text-slate-400 mb-1">OpenAI API Key</label>
                <input
                  type="password"
                  value={openAiKey}
                  onChange={(e) => setOpenAiKey(e.target.value)}
                  placeholder="sk-..."
                  className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>
          </section>

          <section className="border-t border-slate-200 dark:border-slate-800 pt-6">
            <label className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase mb-4">
              <Brain size={16} className="text-indigo-500" />
              Memory
            </label>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-medium text-slate-900 dark:text-white">Enable long-term memory</h4>
                  <p className="text-xs text-slate-400">Jarvis recalls past conversations to provide continuity.</p>
                </div>
                <button
                  onClick={toggleMemory}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${
                    isEnabled ? 'bg-indigo-600' : 'bg-slate-200 dark:bg-slate-700'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      isEnabled ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>

              <div className="flex items-center justify-between p-3.5 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-800/80">
                <div className="text-xs text-slate-500 dark:text-slate-400">
                  Memories stored: <span className="font-semibold text-slate-900 dark:text-white">{memories.length}</span>
                </div>
                {isConfirmingClear ? (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        clearAllMemories()
                        setIsConfirmingClear(false)
                      }}
                      className="text-xs bg-red-600 hover:bg-red-700 text-white px-2.5 py-1.5 rounded-lg font-medium transition-colors"
                    >
                      Yes, Clear
                    </button>
                    <button
                      onClick={() => setIsConfirmingClear(false)}
                      className="text-xs bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 px-2.5 py-1.5 rounded-lg font-medium transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setIsConfirmingClear(true)}
                    disabled={memories.length === 0}
                    className="flex items-center gap-1.5 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/20 disabled:opacity-40 disabled:hover:bg-transparent px-2.5 py-1.5 rounded-lg font-medium transition-colors"
                  >
                    <Trash2 size={14} />
                    Clear all memories
                  </button>
                )}
              </div>
            </div>
          </section>

          <section className="border-t border-slate-200 dark:border-slate-800 pt-6">
            <label className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase mb-4">
              <Puzzle size={16} className="text-indigo-500" />
              Plugins
            </label>
            <div className="flex items-center justify-between p-3.5 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-800/80">
              <div className="text-xs text-slate-500 dark:text-slate-400">
                Installed plugins: <span className="font-semibold text-slate-900 dark:text-white">{plugins.length}</span>
              </div>
              <button
                onClick={() => {
                  onClose()
                  onOpenPlugins()
                }}
                className="flex items-center gap-1.5 text-xs text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/20 px-3 py-1.5 rounded-lg font-semibold transition-colors"
              >
                Manage Plugins
              </button>
            </div>
          </section>

          <section className="pt-4 border-t border-slate-200 dark:border-slate-800">
            <div className="flex justify-between items-center text-[10px] text-slate-400">
              <span>Version 1.0.0</span>
              <span>Shipwright Engineering</span>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

export default SettingsModal
