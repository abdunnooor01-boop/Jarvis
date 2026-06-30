import React from 'react'
import { X, Moon, Sun, Monitor } from 'lucide-react'
import { useSettingsStore } from '../stores/settings'

interface SettingsModalProps {
  onClose: () => void
}

const SettingsModal: React.FC<SettingsModalProps> = ({ onClose }) => {
  const { theme, setTheme, openAiKey, setOpenAiKey } = useSettingsStore()

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
