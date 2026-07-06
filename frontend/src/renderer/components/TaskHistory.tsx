import React, { useState, useEffect } from 'react'
import {
  X,
  Search,
  Calendar,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Slash,
  ChevronDown,
  ChevronUp,
  Terminal,
  ExternalLink,
  History,
  SkipForward
} from 'lucide-react'
import { useTaskStore, TaskPlan, TaskStep } from '../stores/tasks'

interface TaskHistoryProps {
  onClose: () => void
}

export const TaskHistory: React.FC<TaskHistoryProps> = ({ onClose }) => {
  const { plans, fetchPlans, isLoading, error, setActivePlan } = useTaskStore()
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedPlans, setExpandedSteps] = useState<Record<string, boolean>>({})

  useEffect(() => {
    fetchPlans()
  }, [])

  const togglePlanExpanded = (planId: string) => {
    setExpandedSteps((prev) => ({
      ...prev,
      [planId]: !prev[planId]
    }))
  }

  // Filter plans based on search query
  const filteredPlans = plans.filter((plan) => {
    const query = searchQuery.toLowerCase()
    return (
      plan.goal.toLowerCase().includes(query) ||
      plan.status.toLowerCase().includes(query) ||
      plan.steps.some((step) =>
        step.description.toLowerCase().includes(query) ||
        step.tool_name.toLowerCase().includes(query)
      )
    )
  })

  const getStatusStyle = (status: string) => {
    switch (status) {
      case 'completed':
        return {
          bg: 'bg-green-500/10 text-green-500 border-green-500/20',
          icon: <CheckCircle size={14} />
        }
      case 'failed':
        return {
          bg: 'bg-red-500/10 text-red-500 border-red-500/20',
          icon: <XCircle size={14} />
        }
      case 'cancelled':
        return {
          bg: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
          icon: <Slash size={14} />
        }
      case 'paused':
        return {
          bg: 'bg-amber-500/10 text-amber-500 border-amber-500/20',
          icon: <AlertCircle size={14} />
        }
      case 'running':
        return {
          bg: 'bg-green-500/10 text-green-500 border-green-500/20 animate-pulse',
          icon: <ActivityIcon />
        }
      default:
        return {
          bg: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
          icon: <Clock size={14} />
        }
    }
  }

  const getStepStatusIcon = (stepStatus: TaskStep['status']) => {
    switch (stepStatus) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />
      case 'skipped':
        return <SkipForward className="w-4 h-4 text-amber-500" />
      case 'running':
        return <LoaderIcon />
      case 'cancelled':
        return <Slash className="w-4 h-4 text-slate-500" />
      default:
        return <div className="w-3.5 h-3.5 rounded-full border-2 border-slate-300 dark:border-slate-700" />
    }
  }

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr)
      return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    } catch (e) {
      return dateStr
    }
  }

  const getDuration = (start?: string, end?: string) => {
    if (!start || !end) return null
    try {
      const ms = new Date(end).getTime() - new Date(start).getTime()
      if (ms < 0) return null
      const sec = Math.floor(ms / 1000)
      if (sec < 60) return `${sec}s`
      const min = Math.floor(sec / 60)
      const remSec = sec % 60
      return `${min}m ${remSec}s`
    } catch (e) {
      return null
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-4xl h-[85vh] bg-white dark:bg-slate-900 rounded-2xl shadow-2xl overflow-hidden flex flex-col border border-slate-200 dark:border-slate-800">
        {/* Header */}
        <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-950/20">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-500 flex items-center justify-center border border-indigo-500/10">
              <History size={20} />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900 dark:text-white">Task Execution History</h2>
              <p className="text-xs text-slate-400">Review and inspect autonomous goal plans and steps</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Filter Toolbar */}
        <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex gap-3 bg-slate-50/30 dark:bg-slate-950/5">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search plans by goal, status, or tool name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-white rounded-xl pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 border border-transparent dark:border-slate-800/40"
            />
          </div>
        </div>

        {/* Body content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {isLoading && plans.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mb-3"></div>
              <p className="text-sm">Loading history...</p>
            </div>
          ) : error ? (
            <div className="h-full flex flex-col items-center justify-center text-red-500 py-12 space-y-2">
              <AlertCircle size={28} />
              <p className="text-sm font-medium">{error}</p>
              <button
                onClick={() => fetchPlans()}
                className="mt-2 text-xs bg-indigo-600 text-white px-3.5 py-1.5 rounded-lg font-semibold hover:bg-indigo-700 transition-colors"
              >
                Retry Fetch
              </button>
            </div>
          ) : filteredPlans.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 py-16 space-y-3">
              <History size={36} className="opacity-40" />
              <p className="text-sm font-medium">No plans found</p>
              <p className="text-xs text-slate-500">Run a goal with the /plan command to get started.</p>
            </div>
          ) : (
            filteredPlans.map((plan) => {
              const isExpanded = !!expandedPlans[plan.id]
              const statusStyle = getStatusStyle(plan.status)
              const duration = getDuration(plan.started_at, plan.completed_at)

              return (
                <div
                  key={plan.id}
                  className="border border-slate-200 dark:border-slate-800 rounded-2xl bg-white dark:bg-slate-950 overflow-hidden shadow-sm hover:shadow-md dark:shadow-none transition-shadow"
                >
                  {/* Plan Card Summary */}
                  <div className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-50/20 dark:bg-slate-900/10">
                    <div className="flex-1 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full border uppercase tracking-wider ${statusStyle.bg}`}>
                          {statusStyle.icon}
                          {plan.status}
                        </span>
                        <span className="text-xs text-slate-400 flex items-center gap-1 font-medium">
                          <Calendar size={13} />
                          {formatDate(plan.created_at)}
                        </span>
                        {duration && (
                          <span className="text-xs text-slate-400 flex items-center gap-1 font-medium">
                            <Clock size={13} />
                            Duration: {duration}
                          </span>
                        )}
                        <span className="text-xs text-slate-400">
                          {plan.completed_steps} of {plan.total_steps} steps succeeded
                        </span>
                      </div>
                      <h3 className="text-sm font-semibold text-slate-900 dark:text-white leading-relaxed">
                        {plan.goal}
                      </h3>
                    </div>

                    <div className="flex items-center gap-2.5 flex-shrink-0 self-end md:self-auto">
                      <button
                        onClick={() => {
                          setActivePlan(plan)
                          onClose()
                        }}
                        className="flex items-center gap-1 text-xs bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 px-3 py-1.5 rounded-lg font-bold border border-indigo-500/10 transition-colors"
                      >
                        <ExternalLink size={13} />
                        Inspect Plan
                      </button>
                      <button
                        onClick={() => togglePlanExpanded(plan.id)}
                        className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                      >
                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </button>
                    </div>
                  </div>

                  {/* Expanded Step Details Accordion */}
                  {isExpanded && (
                    <div className="border-t border-slate-200 dark:border-slate-800 bg-slate-50/10 dark:bg-slate-950/20 p-4 space-y-3">
                      <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Steps History</div>
                      <div className="space-y-2">
                        {plan.steps.map((step) => (
                          <div
                            key={step.id}
                            className="bg-white dark:bg-slate-900 p-3 rounded-xl border border-slate-100 dark:border-slate-800/60 flex items-start gap-3 shadow-xs"
                          >
                            <div className="mt-0.5">{getStepStatusIcon(step.status)}</div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center flex-wrap gap-2 text-xs">
                                <span className="font-bold text-slate-400">Step {step.step_number}</span>
                                <span className="bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-mono text-[10px] px-1.5 py-0.5 rounded flex items-center gap-1">
                                  <Terminal size={10} />
                                  {step.tool_name}
                                </span>
                              </div>
                              <p className="text-xs text-slate-700 dark:text-slate-200 mt-1 font-medium leading-normal">
                                {step.description}
                              </p>
                              {step.error && (
                                <div className="mt-2 text-[11px] font-mono text-red-600 dark:text-red-400 bg-red-500/5 p-2 rounded-lg border border-red-500/10 overflow-x-auto">
                                  {step.error}
                                </div>
                              )}
                              {step.result && (
                                <div className="mt-2 space-y-1">
                                  <div className="text-[10px] font-semibold text-green-500">Output Summary</div>
                                  <pre className="text-[11px] font-mono text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-950 p-2.5 rounded-lg border border-slate-100 dark:border-slate-800/40 overflow-x-auto max-h-32 overflow-y-auto">
                                    {typeof step.result === 'string'
                                      ? step.result
                                      : JSON.stringify(step.result, null, 2)}
                                  </pre>
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}

// Inline support helpers for animation & loading
const ActivityIcon = () => (
  <svg className="animate-spin h-3.5 w-3.5 text-green-500" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
  </svg>
)

const LoaderIcon = () => (
  <svg className="animate-spin h-4 w-4 text-green-500" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
  </svg>
)
