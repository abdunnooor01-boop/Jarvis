import React, { useState, useEffect, useRef } from 'react'
import {
  X,
  Search,
  Activity,
  Database,
  Cpu,
  Terminal,
  RefreshCw,
  Clock,
  Shield,
  Users,
  MessageSquare,
  Puzzle,
  History,
  FileText,
  Info,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  CheckCircle2,
  XCircle,
  HelpCircle
} from 'lucide-react'
import { useDevStore, DevTool, AuditLogItem } from '../stores/dev'

interface DevConsoleProps {
  onClose: () => void
}

type TabType = 'health' | 'metrics' | 'tools' | 'logs' | 'system'

export const DevConsole: React.FC<DevConsoleProps> = ({ onClose }) => {
  const {
    health,
    metrics,
    systemInfo,
    tools,
    logs,
    healthLoading,
    metricsLoading,
    systemInfoLoading,
    toolsLoading,
    logsLoading,
    error,
    fetchHealth,
    fetchMetrics,
    fetchSystemInfo,
    fetchTools,
    fetchLogs
  } = useDevStore()

  const [activeTab, setActiveTab] = useState<TabType>('health')
  const [autoRefresh, setAutoRefresh] = useState(false)
  const autoRefreshTimer = useRef<NodeJS.Timeout | null>(null)

  // Accordion for tools and logs
  const [expandedTool, setExpandedTool] = useState<string | null>(null)
  const [expandedLog, setExpandedLog] = useState<number | null>(null)

  // Log filter states
  const [logLevel, setLogLevel] = useState<string>('')
  const [logSearch, setLogSearch] = useState<string>('')
  const [logPage, setLogPage] = useState<number>(1)

  // Tool filter states
  const [toolSearch, setToolSearch] = useState<string>('')

  // Initial data loading
  useEffect(() => {
    loadTabData(activeTab)
  }, [activeTab])

  // Handle active logs filters & pagination
  useEffect(() => {
    if (activeTab === 'logs') {
      fetchLogs({ level: logLevel || undefined, search: logSearch || undefined, page: logPage })
    }
  }, [logLevel, logPage])

  // Auto-refresh mechanism
  useEffect(() => {
    if (autoRefresh) {
      autoRefreshTimer.current = setInterval(() => {
        if (activeTab === 'health') {
          fetchHealth()
        } else if (activeTab === 'metrics') {
          fetchMetrics()
        } else if (activeTab === 'logs') {
          fetchLogs({ level: logLevel || undefined, search: logSearch || undefined, page: logPage })
        }
      }, 5000)
    } else {
      if (autoRefreshTimer.current) {
        clearInterval(autoRefreshTimer.current)
      }
    }

    return () => {
      if (autoRefreshTimer.current) {
        clearInterval(autoRefreshTimer.current)
      }
    }
  }, [autoRefresh, activeTab, logLevel, logSearch, logPage])

  const loadTabData = (tab: TabType) => {
    switch (tab) {
      case 'health':
        fetchHealth()
        break
      case 'metrics':
        fetchMetrics()
        break
      case 'tools':
        fetchTools()
        break
      case 'logs':
        fetchLogs({ level: logLevel || undefined, search: logSearch || undefined, page: logPage })
        break
      case 'system':
        fetchSystemInfo()
        break
    }
  }

  const handleManualRefresh = () => {
    loadTabData(activeTab)
  }

  const formatUptime = (seconds?: number) => {
    if (seconds === undefined) return 'N/A'
    const days = Math.floor(seconds / (24 * 3600))
    const hours = Math.floor((seconds % (24 * 3600)) / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = Math.floor(seconds % 60)

    const parts = []
    if (days > 0) parts.push(`${days}d`)
    if (hours > 0) parts.push(`${hours}h`)
    if (minutes > 0) parts.push(`${minutes}m`)
    parts.push(`${secs}s`)

    return parts.join(' ')
  }

  const handleLogSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setLogPage(1)
    fetchLogs({ level: logLevel || undefined, search: logSearch || undefined, page: 1 })
  }

  // Filter tools based on search
  const filteredTools = tools.filter(
    (tool) =>
      tool.name.toLowerCase().includes(toolSearch.toLowerCase()) ||
      tool.description.toLowerCase().includes(toolSearch.toLowerCase())
  )

  const isTabLoading = (tab: TabType) => {
    switch (tab) {
      case 'health': return healthLoading
      case 'metrics': return metricsLoading
      case 'tools': return toolsLoading
      case 'logs': return logsLoading
      case 'system': return systemInfoLoading
      default: return false
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fadeIn">
      <div className="w-full max-w-5xl h-[85vh] bg-white dark:bg-slate-900 rounded-2xl shadow-2xl overflow-hidden flex flex-col border border-slate-200 dark:border-slate-800">
        {/* Header */}
        <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-950/20">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-500 flex items-center justify-center border border-indigo-500/10 animate-pulse">
              <Terminal size={20} />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                Developer Console Mode
              </h2>
              <p className="text-xs text-slate-400">Introspect services, system diagnostics, registered tools and live audit logs</p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Auto Refresh Toggle */}
            {(activeTab === 'health' || activeTab === 'metrics' || activeTab === 'logs') && (
              <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-slate-500 dark:text-slate-400">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 dark:bg-slate-950 dark:border-slate-800"
                />
                Auto-Refresh (5s)
              </label>
            )}

            {/* Manual Refresh */}
            <button
              onClick={handleManualRefresh}
              disabled={isTabLoading(activeTab)}
              className="p-1.5 text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors disabled:opacity-50"
              title="Refresh Current Tab"
            >
              <RefreshCw size={16} className={isTabLoading(activeTab) ? 'animate-spin' : ''} />
            </button>

            {/* Close Button */}
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex border-b border-slate-200 dark:border-slate-800 bg-slate-50/25 dark:bg-slate-950/10 px-4">
          {(['health', 'metrics', 'tools', 'logs', 'system'] as TabType[]).map((tab) => {
            const isActive = activeTab === tab
            return (
              <button
                key={tab}
                onClick={() => {
                  setActiveTab(tab)
                  setLogPage(1)
                  setExpandedTool(null)
                  setExpandedLog(null)
                }}
                className={`px-4 py-3 text-sm font-medium border-b-2 transition-all flex items-center gap-2 capitalize ${
                  isActive
                    ? 'border-indigo-600 text-indigo-600 dark:border-indigo-500 dark:text-indigo-400'
                    : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
                }`}
              >
                {tab === 'health' && <Activity size={15} />}
                {tab === 'metrics' && <Cpu size={15} />}
                {tab === 'tools' && <Shield size={15} />}
                {tab === 'logs' && <FileText size={15} />}
                {tab === 'system' && <Info size={15} />}
                {tab === 'system' ? 'System Info' : tab}
              </button>
            )
          })}
        </div>

        {/* Tab Content Body */}
        <div className="flex-1 overflow-y-auto p-6 bg-white dark:bg-slate-900/40">
          {error && (
            <div className="mb-4 p-3.5 rounded-xl bg-red-500/10 text-red-500 border border-red-500/10 flex items-center gap-3 text-sm">
              <AlertCircle size={18} className="flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* HEALTH TAB */}
          {activeTab === 'health' && (
            <div className="space-y-6">
              {healthLoading && !health ? (
                <div className="py-12 flex flex-col items-center justify-center text-slate-400">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mb-2"></div>
                  <p className="text-sm">Fetching system health status...</p>
                </div>
              ) : health ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Status Indicator Card */}
                  <div className="bg-slate-50 dark:bg-slate-950/30 p-5 rounded-2xl border border-slate-200/60 dark:border-slate-800/60 flex flex-col justify-between">
                    <div>
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">Overall System Status</h3>
                      <div className="flex items-center gap-3 mt-2">
                        {health.status === 'healthy' ? (
                          <>
                            <div className="w-3.5 h-3.5 rounded-full bg-green-500 animate-ping absolute" />
                            <div className="w-3.5 h-3.5 rounded-full bg-green-500 relative" />
                            <span className="text-xl font-bold text-slate-900 dark:text-white capitalize">{health.status}</span>
                          </>
                        ) : (
                          <>
                            <div className="w-3.5 h-3.5 rounded-full bg-red-500 animate-ping absolute" />
                            <div className="w-3.5 h-3.5 rounded-full bg-red-500 relative" />
                            <span className="text-xl font-bold text-slate-900 dark:text-white capitalize">{health.status}</span>
                          </>
                        )}
                      </div>
                    </div>

                    <div className="mt-8 border-t border-slate-200 dark:border-slate-800/80 pt-4 grid grid-cols-2 gap-4">
                      <div>
                        <div className="text-xs text-slate-400 flex items-center gap-1">
                          <Clock size={12} /> System Uptime
                        </div>
                        <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 mt-1">
                          {formatUptime(health.uptime_seconds)}
                        </p>
                      </div>
                      <div>
                        <div className="text-xs text-slate-400">Last Checked</div>
                        <p className="text-xs font-mono text-slate-600 dark:text-slate-300 mt-1">
                          {new Date(health.timestamp * 1000).toLocaleString()}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Core Services Cards */}
                  <div className="space-y-4">
                    <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200">Core Services Connectivity</h3>

                    {/* Database health */}
                    <div className="bg-slate-50 dark:bg-slate-950/30 p-4 rounded-xl border border-slate-200/60 dark:border-slate-800/60 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-lg bg-emerald-500/10 text-emerald-500 flex items-center justify-center">
                          <Database size={16} />
                        </div>
                        <div>
                          <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">Database connection</h4>
                          <p className="text-xs font-mono text-slate-400 uppercase">{health.services.database.type || 'SQLite'}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {health.services.database.status === 'healthy' ? (
                          <>
                            <span className="text-xs font-medium text-emerald-500">Connected</span>
                            <CheckCircle2 size={16} className="text-emerald-500" />
                          </>
                        ) : (
                          <>
                            <span className="text-xs font-medium text-red-500">Disconnected</span>
                            <XCircle size={16} className="text-red-500" />
                          </>
                        )}
                      </div>
                    </div>

                    {/* API server health */}
                    <div className="bg-slate-50 dark:bg-slate-950/30 p-4 rounded-xl border border-slate-200/60 dark:border-slate-800/60 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-lg bg-blue-500/10 text-blue-500 flex items-center justify-center">
                          <Cpu size={16} />
                        </div>
                        <div>
                          <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">API endpoints status</h4>
                          <p className="text-xs text-slate-400">FastAPI Server</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {health.services.api.status === 'healthy' ? (
                          <>
                            <span className="text-xs font-medium text-emerald-500">Healthy</span>
                            <CheckCircle2 size={16} className="text-emerald-500" />
                          </>
                        ) : (
                          <>
                            <span className="text-xs font-medium text-red-500">Degraded</span>
                            <XCircle size={16} className="text-red-500" />
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="py-12 text-center text-slate-400">No health data received.</div>
              )}
            </div>
          )}

          {/* METRICS TAB */}
          {activeTab === 'metrics' && (
            <div className="space-y-6">
              {metricsLoading && !metrics ? (
                <div className="py-12 flex flex-col items-center justify-center text-slate-400">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mb-2"></div>
                  <p className="text-sm">Retrieving real-time metrics...</p>
                </div>
              ) : metrics ? (
                <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                  {/* Total Users */}
                  <div className="bg-slate-50 dark:bg-slate-950/30 p-5 rounded-2xl border border-slate-200/60 dark:border-slate-800/60 flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-indigo-500/10 text-indigo-500 flex items-center justify-center">
                      <Users size={22} />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Users</p>
                      <h3 className="text-2xl font-bold text-slate-800 dark:text-white mt-1">{metrics.users.total}</h3>
                    </div>
                  </div>

                  {/* Conversations */}
                  <div className="bg-slate-50 dark:bg-slate-950/30 p-5 rounded-2xl border border-slate-200/60 dark:border-slate-800/60 flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-blue-500/10 text-blue-500 flex items-center justify-center">
                      <MessageSquare size={22} />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Conversations</p>
                      <h3 className="text-2xl font-bold text-slate-800 dark:text-white mt-1">{metrics.conversations.total}</h3>
                    </div>
                  </div>

                  {/* Messages */}
                  <div className="bg-slate-50 dark:bg-slate-950/30 p-5 rounded-2xl border border-slate-200/60 dark:border-slate-800/60 flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-emerald-500/10 text-emerald-500 flex items-center justify-center">
                      <FileText size={22} />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Messages</p>
                      <h3 className="text-2xl font-bold text-slate-800 dark:text-white mt-1">{metrics.messages.total}</h3>
                    </div>
                  </div>

                  {/* Autonomous Task Plans */}
                  <div className="bg-slate-50 dark:bg-slate-950/30 p-5 rounded-2xl border border-slate-200/60 dark:border-slate-800/60 flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-purple-500/10 text-purple-500 flex items-center justify-center">
                      <History size={22} />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Task Plans</p>
                      <h3 className="text-2xl font-bold text-slate-800 dark:text-white mt-1">{metrics.task_plans.total}</h3>
                    </div>
                  </div>

                  {/* Audit Logs */}
                  <div className="bg-slate-50 dark:bg-slate-950/30 p-5 rounded-2xl border border-slate-200/60 dark:border-slate-800/60 flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-amber-500/10 text-amber-500 flex items-center justify-center">
                      <Shield size={22} />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Audit Log Entries</p>
                      <h3 className="text-2xl font-bold text-slate-800 dark:text-white mt-1">{metrics.audit_log_entries.total}</h3>
                    </div>
                  </div>

                  {/* Plugins Count */}
                  <div className="bg-slate-50 dark:bg-slate-950/30 p-5 rounded-2xl border border-slate-200/60 dark:border-slate-800/60 flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-pink-500/10 text-pink-500 flex items-center justify-center">
                      <Puzzle size={22} />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Installed Plugins</p>
                      <h3 className="text-2xl font-bold text-slate-800 dark:text-white mt-1">{metrics.plugins.total}</h3>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="py-12 text-center text-slate-400">No metrics data available.</div>
              )}
            </div>
          )}

          {/* TOOLS INTROSPECTION TAB */}
          {activeTab === 'tools' && (
            <div className="space-y-4">
              {/* Search Toolbar */}
              <div className="relative">
                <Search className="absolute left-3 top-2.5 h-4.5 w-4.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search registered tools by name or description..."
                  value={toolSearch}
                  onChange={(e) => setToolSearch(e.target.value)}
                  className="w-full bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white rounded-xl pl-10 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 border border-slate-200 dark:border-slate-800/60"
                />
              </div>

              {toolsLoading && tools.length === 0 ? (
                <div className="py-12 flex flex-col items-center justify-center text-slate-400">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mb-2"></div>
                  <p className="text-sm">Scanning registered tools...</p>
                </div>
              ) : filteredTools.length === 0 ? (
                <div className="py-12 text-center text-slate-400 flex flex-col items-center justify-center space-y-2">
                  <HelpCircle size={28} className="opacity-40" />
                  <p className="text-sm">No tools found matching search criteria</p>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-xs text-slate-400 font-semibold mb-1">
                    Showing {filteredTools.length} of {tools.length} Registered Tools
                  </p>

                  {filteredTools.map((tool) => {
                    const isExpanded = expandedTool === tool.name
                    return (
                      <div
                        key={tool.name}
                        className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden bg-slate-50/30 dark:bg-slate-950/5 hover:border-slate-300 dark:hover:border-slate-700 transition-colors"
                      >
                        {/* Tool Item Header */}
                        <button
                          onClick={() => setExpandedTool(isExpanded ? null : tool.name)}
                          className="w-full p-4 flex items-center justify-between text-left"
                        >
                          <div className="flex items-center gap-3">
                            <div className="px-2.5 py-1 rounded bg-indigo-500/10 text-indigo-500 dark:text-indigo-400 font-mono text-xs font-semibold border border-indigo-500/10">
                              {tool.name}
                            </div>
                            <span className="text-xs text-slate-500 dark:text-slate-400 line-clamp-1 max-w-xl">
                              {tool.description}
                            </span>
                          </div>
                          {isExpanded ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
                        </button>

                        {/* Expandable JSON Schema details */}
                        {isExpanded && (
                          <div className="p-4 border-t border-slate-200 dark:border-slate-800/80 bg-slate-50/50 dark:bg-slate-950/25 space-y-4 font-mono text-xs text-slate-700 dark:text-slate-300">
                            <div>
                              <span className="font-bold text-slate-800 dark:text-slate-200 block mb-1">Full Description:</span>
                              <p className="font-sans text-slate-600 dark:text-slate-400 whitespace-pre-wrap">
                                {tool.description}
                              </p>
                            </div>
                            <div>
                              <span className="font-bold text-slate-800 dark:text-slate-200 block mb-1">JSON Input Schema:</span>
                              <pre className="p-3 rounded bg-slate-100 dark:bg-slate-950 text-slate-800 dark:text-slate-300 overflow-x-auto max-h-60 border border-slate-200 dark:border-slate-800">
                                {JSON.stringify(tool.parameters, null, 2)}
                              </pre>
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* LOG VIEWER TAB */}
          {activeTab === 'logs' && (
            <div className="space-y-4">
              {/* Filter Form */}
              <form onSubmit={handleLogSearchSubmit} className="flex flex-col md:flex-row gap-3">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Search logs by action, resource, details..."
                    value={logSearch}
                    onChange={(e) => setLogSearch(e.target.value)}
                    className="w-full bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white rounded-xl pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 border border-slate-200 dark:border-slate-800/60"
                  />
                </div>

                <div className="flex gap-2">
                  <select
                    value={logLevel}
                    onChange={(e) => {
                      setLogLevel(e.target.value)
                      setLogPage(1)
                    }}
                    className="bg-slate-50 dark:bg-slate-950 text-slate-800 dark:text-slate-200 text-sm rounded-xl px-3 py-2 border border-slate-200 dark:border-slate-800/60 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="">All Events</option>
                    <option value="auth_login">Auth Login</option>
                    <option value="auth_logout">Auth Logout</option>
                    <option value="tool_execute">Tool Exec</option>
                    <option value="plugin_toggle">Plugin Toggle</option>
                    <option value="task_create">Task Create</option>
                    <option value="task_step">Task Step</option>
                  </select>

                  <button
                    type="submit"
                    className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-4 py-2 rounded-xl transition-colors"
                  >
                    Search
                  </button>
                </div>
              </form>

              {logsLoading && (!logs || logs.items.length === 0) ? (
                <div className="py-12 flex flex-col items-center justify-center text-slate-400">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mb-2"></div>
                  <p className="text-sm">Querying system audit log entries...</p>
                </div>
              ) : !logs || logs.items.length === 0 ? (
                <div className="py-12 text-center text-slate-400 flex flex-col items-center justify-center space-y-2">
                  <FileText size={28} className="opacity-40" />
                  <p className="text-sm">No log entries found</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Logs Table-like Accordion */}
                  <div className="space-y-2.5">
                    {logs.items.map((log) => {
                      const isExpanded = expandedLog === log.id
                      const isSuccess = log.status === 'success'

                      return (
                        <div
                          key={log.id}
                          className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden bg-slate-50/20 dark:bg-slate-950/5 hover:border-slate-300 dark:hover:border-slate-700 transition-colors"
                        >
                          {/* Row Header */}
                          <button
                            onClick={() => setExpandedLog(isExpanded ? null : log.id)}
                            className="w-full p-3 flex flex-col md:flex-row md:items-center justify-between text-left gap-2 text-xs"
                          >
                            <div className="flex flex-wrap items-center gap-2 font-mono">
                              <span className="text-slate-400 whitespace-nowrap">
                                {new Date(log.created_at).toLocaleTimeString()}
                              </span>
                              <span className="px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-500 dark:text-indigo-400 font-semibold border border-indigo-500/5">
                                {log.event_type}
                              </span>
                              <span className="text-slate-800 dark:text-slate-200 font-semibold">
                                {log.action}
                              </span>
                              <span className="text-slate-500 dark:text-slate-400">
                                {log.resource}
                              </span>
                            </div>

                            <div className="flex items-center gap-3">
                              <span className={`px-1.5 py-0.5 rounded-full font-semibold border ${
                                isSuccess
                                  ? 'bg-green-500/10 text-green-500 border-green-500/10'
                                  : 'bg-red-500/10 text-red-500 border-red-500/10'
                              }`}>
                                {log.status}
                              </span>
                              {isExpanded ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
                            </div>
                          </button>

                          {/* Expandable full audit log JSON details */}
                          {isExpanded && (
                            <div className="p-4 border-t border-slate-200 dark:border-slate-800/80 bg-slate-100/50 dark:bg-slate-950/20 font-mono text-xs space-y-3">
                              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-slate-500">
                                <div>
                                  <span className="block text-xs font-semibold text-slate-400">Log ID</span>
                                  <span className="text-slate-800 dark:text-slate-300 font-mono text-xs mt-0.5 block">{log.id}</span>
                                </div>
                                <div>
                                  <span className="block text-xs font-semibold text-slate-400">Actor IP</span>
                                  <span className="text-slate-800 dark:text-slate-300 font-mono text-xs mt-0.5 block">{log.actor_ip || 'N/A'}</span>
                                </div>
                                <div>
                                  <span className="block text-xs font-semibold text-slate-400">Actor ID</span>
                                  <span className="text-slate-800 dark:text-slate-300 font-mono text-xs mt-0.5 block">{log.actor_id || 'System'}</span>
                                </div>
                                <div>
                                  <span className="block text-xs font-semibold text-slate-400">Created At</span>
                                  <span className="text-slate-800 dark:text-slate-300 font-mono text-xs mt-0.5 block">{log.created_at}</span>
                                </div>
                              </div>
                              <div>
                                <span className="block text-xs font-semibold text-slate-400 mb-1.5">Action Parameters / Details:</span>
                                <pre className="p-3 rounded bg-slate-100 dark:bg-slate-950 text-slate-800 dark:text-slate-300 overflow-x-auto max-h-60 border border-slate-200 dark:border-slate-800/80">
                                  {JSON.stringify(log.details, null, 2)}
                                </pre>
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>

                  {/* Pagination Footer */}
                  <div className="flex items-center justify-between border-t border-slate-200 dark:border-slate-800 pt-4 text-xs">
                    <span className="text-slate-500">
                      Showing Page {logs.page} of {logs.pages} ({logs.total} total logs)
                    </span>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setLogPage((p) => Math.max(1, p - 1))}
                        disabled={logPage === 1 || logsLoading}
                        className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-950 transition-colors disabled:opacity-40"
                      >
                        Previous
                      </button>
                      <button
                        onClick={() => setLogPage((p) => Math.min(logs.pages, p + 1))}
                        disabled={logPage === logs.pages || logsLoading}
                        className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-950 transition-colors disabled:opacity-40"
                      >
                        Next
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* SYSTEM INFO TAB */}
          {activeTab === 'system' && (
            <div className="space-y-6">
              {systemInfoLoading && !systemInfo ? (
                <div className="py-12 flex flex-col items-center justify-center text-slate-400">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mb-2"></div>
                  <p className="text-sm">Fetching detailed system specifications...</p>
                </div>
              ) : systemInfo ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Host, OS, Runtime Details */}
                  <div className="space-y-5">
                    <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                      <Cpu size={16} className="text-indigo-500" /> Server Runtime Environment
                    </h3>

                    <div className="bg-slate-50 dark:bg-slate-950/30 p-5 rounded-2xl border border-slate-200/60 dark:border-slate-800/60 space-y-4 text-xs font-mono">
                      <div>
                        <span className="text-slate-400 block uppercase tracking-wider text-[10px]">App Name / Version</span>
                        <p className="text-slate-800 dark:text-slate-200 font-bold mt-0.5">
                          {systemInfo.application.name} (v{systemInfo.application.version})
                        </p>
                      </div>
                      <div>
                        <span className="text-slate-400 block uppercase tracking-wider text-[10px]">Environment / Debug</span>
                        <p className="text-slate-800 dark:text-slate-200 mt-0.5 font-bold">
                          {systemInfo.application.environment} (debug: {systemInfo.application.debug ? 'true' : 'false'})
                        </p>
                      </div>
                      <div>
                        <span className="text-slate-400 block uppercase tracking-wider text-[10px]">Python Engine</span>
                        <p className="text-slate-800 dark:text-slate-200 mt-0.5 whitespace-pre-wrap">
                          {systemInfo.runtime.python_version}
                        </p>
                      </div>
                      <div>
                        <span className="text-slate-400 block uppercase tracking-wider text-[10px]">Platform OS</span>
                        <p className="text-slate-800 dark:text-slate-200 mt-0.5">
                          {systemInfo.runtime.platform}
                        </p>
                      </div>
                      <div>
                        <span className="text-slate-400 block uppercase tracking-wider text-[10px]">Hostname</span>
                        <p className="text-slate-800 dark:text-slate-200 mt-0.5">
                          {systemInfo.runtime.hostname}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Sanitized Configurations details */}
                  <div className="space-y-5">
                    <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                      <Shield size={16} className="text-emerald-500" /> Sanitized Configurations & API Keys
                    </h3>

                    <div className="bg-slate-50 dark:bg-slate-950/30 p-5 rounded-2xl border border-slate-200/60 dark:border-slate-800/60 space-y-4 text-xs font-mono">
                      <div>
                        <span className="text-slate-400 block uppercase tracking-wider text-[10px]">Database Engine Type</span>
                        <p className="text-slate-800 dark:text-slate-200 font-bold mt-0.5 uppercase">
                          {systemInfo.configuration.database_type}
                        </p>
                      </div>
                      <div>
                        <span className="text-slate-400 block uppercase tracking-wider text-[10px]">LLM Provider Model</span>
                        <p className="text-slate-800 dark:text-slate-200 font-bold mt-0.5 uppercase text-indigo-500">
                          {systemInfo.configuration.llm_model}
                        </p>
                      </div>
                      <div>
                        <span className="text-slate-400 block uppercase tracking-wider text-[10px]">CORS Allowed Origins</span>
                        <p className="text-slate-800 dark:text-slate-200 mt-0.5">
                          {systemInfo.configuration.cors_origins.join(', ')}
                        </p>
                      </div>
                      <div>
                        <span className="text-slate-400 block uppercase tracking-wider text-[10px]">Configured Credentials Check</span>
                        <div className="grid grid-cols-2 gap-2.5 mt-2">
                          {Object.entries(systemInfo.configuration.api_keys_configured).map(([provider, isConfigured]) => (
                            <div key={provider} className="flex items-center justify-between p-2 rounded bg-slate-100/55 dark:bg-slate-900 border border-slate-200/40 dark:border-slate-800/50">
                              <span className="capitalize">{provider} key</span>
                              {isConfigured ? (
                                <span className="text-[10px] font-bold text-emerald-500">SET</span>
                              ) : (
                                <span className="text-[10px] font-bold text-slate-400">MISSING</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="py-12 text-center text-slate-400">No system info found.</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
