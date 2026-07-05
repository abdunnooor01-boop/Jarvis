import React from 'react'
import { Puzzle, Package, User } from 'lucide-react'
import { Plugin } from '../stores/plugins'

interface PluginCardProps {
  plugin: Plugin
  onToggle?: (name: string) => void
  isDiscover?: boolean
}

export const PluginCard: React.FC<PluginCardProps> = ({ plugin, onToggle, isDiscover = false }) => {
  return (
    <div className="flex flex-col justify-between p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl hover:border-slate-300 dark:hover:border-slate-700 hover:shadow-md transition-all duration-300">
      <div className="space-y-4">
        {/* Header: Icon, Name, Version, Pulsing Dot */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-slate-50 dark:bg-slate-800 text-slate-500 dark:text-slate-400 rounded-xl">
              <Puzzle size={22} className="text-indigo-600 dark:text-indigo-400" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h4 className="font-bold text-slate-900 dark:text-white text-sm tracking-tight">{plugin.name}</h4>
                <span className="px-1.5 py-0.5 text-[10px] font-bold bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 rounded-md border border-slate-200/50 dark:border-slate-700/50">
                  v{plugin.version}
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-slate-400 mt-0.5">
                <User size={12} />
                <span className="truncate max-w-[120px]">{plugin.author}</span>
              </div>
            </div>
          </div>

          {!isDiscover && plugin.enabled && (
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
            </span>
          )}
        </div>

        {/* Description */}
        <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 leading-relaxed min-h-[2rem]">
          {plugin.description || 'No description provided.'}
        </p>
      </div>

      {/* Footer: Toggle/Status or Install button */}
      <div className="flex items-center justify-between pt-4 mt-4 border-t border-slate-100 dark:border-slate-800/80">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-400">
          <Package size={14} />
          <span>{plugin.tool_count || 0} tools</span>
        </div>

        {isDiscover ? (
          <button
            disabled
            className="text-xs bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-400 dark:text-slate-500 px-3 py-1.5 rounded-lg font-bold transition-all"
          >
            Coming soon
          </button>
        ) : (
          <button
            onClick={() => onToggle?.(plugin.name)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${
              plugin.enabled ? 'bg-indigo-600' : 'bg-slate-200 dark:bg-slate-700'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                plugin.enabled ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        )}
      </div>
    </div>
  )
}

export default PluginCard
