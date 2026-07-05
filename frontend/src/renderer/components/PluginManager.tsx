import React, { useEffect, useState } from 'react'
import { X, Search, Puzzle, Compass, RefreshCw, AlertCircle } from 'lucide-react'
import { usePluginStore, Plugin } from '../stores/plugins'
import PluginCard from './PluginCard'

interface PluginManagerProps {
  onClose: () => void
}

const DISCOVER_PLUGINS: Plugin[] = [
  {
    name: 'Weather Forecaster',
    version: '1.0.0',
    description: 'Get live weather conditions and forecasts for any location in real-time.',
    author: 'Meteorology Group',
    enabled: false,
    installed_at: '',
    tool_count: 3
  },
  {
    name: 'Spotify Controller',
    version: '2.1.0',
    description: 'Control your Spotify music playback and search playlists natively.',
    author: 'MusicDevs',
    enabled: false,
    installed_at: '',
    tool_count: 5
  },
  {
    name: 'GitHub Agent',
    version: '1.4.2',
    description: 'Interact with your GitHub repositories, inspect commits, and manage pull requests.',
    author: 'GitCreators',
    enabled: false,
    installed_at: '',
    tool_count: 8
  },
  {
    name: 'Docker Manager',
    version: '1.2.0',
    description: 'Manage and inspect local Docker containers, volumes, and networks.',
    author: 'SysOps Ltd',
    enabled: false,
    installed_at: '',
    tool_count: 6
  }
]

export const PluginManager: React.FC<PluginManagerProps> = ({ onClose }) => {
  const { plugins, isLoading, error, fetchPlugins, togglePlugin } = usePluginStore()
  const [activeTab, setActiveTab] = useState<'installed' | 'discover'>('installed')
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    fetchPlugins()
  }, [fetchPlugins])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const filteredInstalled = plugins.filter(
    (p) =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.description.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const filteredDiscover = DISCOVER_PLUGINS.filter(
    (p) =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.description.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md p-4 md:p-8">
      <div className="w-full max-w-4xl h-[85vh] bg-white dark:bg-slate-950 rounded-2xl shadow-2xl overflow-hidden flex flex-col border border-slate-200 dark:border-slate-800 animate-in fade-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-900 bg-slate-50/50 dark:bg-slate-950/50">
          <div className="flex items-center gap-2">
            <Puzzle className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            <h3 className="font-bold text-lg text-slate-900 dark:text-white">Plugin Manager</h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Search and Tabs controls */}
        <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-900 flex flex-col md:flex-row md:items-center justify-between gap-4">
          {/* Tabs */}
          <div className="flex bg-slate-100 dark:bg-slate-900 p-1 rounded-xl w-fit">
            <button
              onClick={() => setActiveTab('installed')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                activeTab === 'installed'
                  ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
              }`}
            >
              <Puzzle size={14} />
              Installed
              <span className="ml-1 bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 text-[10px] px-1.5 py-0.5 rounded-full">
                {plugins.length}
              </span>
            </button>
            <button
              onClick={() => setActiveTab('discover')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                activeTab === 'discover'
                  ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
              }`}
            >
              <Compass size={14} />
              Discover
            </button>
          </div>

          {/* Search bar */}
          <div className="relative max-w-md w-full">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search plugins by name or description..."
              className="w-full pl-10 pr-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-xs text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all"
            />
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-6 bg-slate-50/30 dark:bg-slate-950/20">
          {error && (
            <div className="mb-6 p-4 bg-red-50 dark:bg-red-950/20 border border-red-200/50 dark:border-red-900/40 rounded-xl flex items-center justify-between text-red-600 dark:text-red-400">
              <div className="flex items-center gap-2.5">
                <AlertCircle size={18} />
                <span className="text-xs font-medium">{error}</span>
              </div>
              <button
                onClick={fetchPlugins}
                className="flex items-center gap-1.5 text-xs bg-red-100 hover:bg-red-200 dark:bg-red-900/30 dark:hover:bg-red-900/50 px-3 py-1.5 rounded-lg font-semibold transition-colors animate-pulse"
              >
                <RefreshCw size={12} />
                Retry
              </button>
            </div>
          )}

          {activeTab === 'installed' ? (
            /* Installed tab content */
            isLoading && plugins.length === 0 ? (
              /* Loading Skeletons */
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-pulse">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-[140px] border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl" />
                ))}
              </div>
            ) : filteredInstalled.length === 0 ? (
              <div className="h-64 flex flex-col items-center justify-center text-slate-400 gap-3">
                <Puzzle size={36} className="text-slate-300 dark:text-slate-700" />
                <p className="text-sm font-semibold">No installed plugins found</p>
                {searchQuery && <p className="text-xs text-slate-500">Try modifying your search query.</p>}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {filteredInstalled.map((plugin) => (
                  <PluginCard
                    key={plugin.name}
                    plugin={plugin}
                    onToggle={togglePlugin}
                  />
                ))}
              </div>
            )
          ) : (
            /* Discover tab content */
            filteredDiscover.length === 0 ? (
              <div className="h-64 flex flex-col items-center justify-center text-slate-400 gap-3">
                <Compass size={36} className="text-slate-300 dark:text-slate-700" />
                <p className="text-sm font-semibold">No matching plugins in marketplace</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {filteredDiscover.map((plugin) => (
                  <PluginCard
                    key={plugin.name}
                    plugin={plugin}
                    isDiscover
                  />
                ))}
              </div>
            )
          )}
        </div>
      </div>
    </div>
  )
}

export default PluginManager
