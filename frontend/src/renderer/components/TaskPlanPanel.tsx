import React, { useState } from 'react'
import {
  Play,
  Pause,
  XCircle,
  CheckCircle2,
  X,
  Circle,
  Loader2,
  ChevronDown,
  ChevronUp,
  Terminal,
  Activity,
  AlertCircle,
  SkipForward
} from 'lucide-react'
import { useTaskStore, TaskStep } from '../stores/tasks'

export const TaskPlanPanel: React.FC = () => {
  const { activePlan, pausePlan, resumePlan, cancelPlan, setActivePlan } = useTaskStore()
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({})

  if (!activePlan) return null

  const {
    id,
    goal,
    status,
    steps,
    total_steps,
    completed_steps,
    failed_steps
  } = activePlan

  const progressPercent = total_steps > 0 ? Math.round((completed_steps / total_steps) * 100) : 0

  const toggleStepExpanded = (stepId: string) => {
    setExpandedSteps((prev) => ({
      ...prev,
      [stepId]: !prev[stepId]
    }))
  }

  const getStatusBadge = (statusStr: string) => {
    switch (statusStr) {
      case 'running':
        return (
          <span className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 bg-green-500/10 text-green-500 border border-green-500/20 rounded-full animate-pulse">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
            Executing
          </span>
        )
      case 'paused':
        return (
          <span className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 bg-amber-500/10 text-amber-500 border border-amber-500/20 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
            Paused
          </span>
        )
      case 'completed':
        return (
          <span className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 bg-indigo-500/10 text-indigo-500 border border-indigo-500/20 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
            Completed
          </span>
        )
      case 'failed':
        return (
          <span className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 bg-red-500/10 text-red-500 border border-red-500/20 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
            Failed
          </span>
        )
      case 'cancelled':
        return (
          <span className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 bg-slate-500/10 text-slate-400 border border-slate-500/20 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
            Cancelled
          </span>
        )
      default:
        return (
          <span className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 bg-slate-500/10 text-slate-400 border border-slate-500/20 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
            Pending
          </span>
        )
    }
  }

  const getStepIcon = (stepStatus: TaskStep['status']) => {
    switch (stepStatus) {
      case 'running':
        return <Loader2 className="w-5 h-5 animate-spin text-green-500 flex-shrink-0" />
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0" />
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
      case 'skipped':
        return <SkipForward className="w-5 h-5 text-amber-500 flex-shrink-0" />
      case 'cancelled':
        return <XCircle className="w-5 h-5 text-slate-500 flex-shrink-0" />
      default:
        return <Circle className="w-5 h-5 text-slate-300 dark:text-slate-700 flex-shrink-0" />
    }
  }

  return (
    <div className="flex flex-col h-full bg-slate-50 dark:bg-slate-950 border-l border-slate-200 dark:border-slate-800 w-96 flex-shrink-0">
      {/* Header */}
      <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={18} className="text-indigo-500 animate-pulse" />
          <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Task Execution</h2>
        </div>
        <button
          onClick={() => setActivePlan(null)}
          className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded transition-colors"
        >
          <X size={18} />
        </button>
      </div>

      {/* Goal & Status Card */}
      <div className="p-4 border-b border-slate-200 dark:border-slate-800 space-y-3 bg-white dark:bg-slate-900/40">
        <div className="flex items-center justify-between">
          <div className="text-xs text-slate-400 font-medium">Goal Description</div>
          {getStatusBadge(status)}
        </div>
        <p className="text-sm font-medium text-slate-700 dark:text-slate-300 leading-relaxed max-h-20 overflow-y-auto pr-1">
          {goal}
        </p>

        {/* Overall Progress */}
        <div className="space-y-1 pt-1">
          <div className="flex justify-between items-center text-xs text-slate-500">
            <span>Progress ({completed_steps}/{total_steps} steps)</span>
            <span className="font-semibold">{progressPercent}%</span>
          </div>
          <div className="h-2 w-full bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-600 transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* Controller Actions */}
        {(status === 'running' || status === 'paused' || status === 'pending' || status === 'approved') && (
          <div className="flex gap-2 pt-2">
            {status === 'paused' ? (
              <button
                onClick={() => resumePlan(id)}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-green-600 hover:bg-green-700 text-white text-xs font-semibold rounded-lg transition-colors shadow-sm shadow-green-600/10"
              >
                <Play size={14} />
                Resume Plan
              </button>
            ) : (
              <button
                onClick={() => pausePlan(id)}
                disabled={status === 'pending'}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition-colors shadow-sm shadow-amber-600/10"
              >
                <Pause size={14} />
                Pause Execution
              </button>
            )}
            <button
              onClick={() => cancelPlan(id)}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-200 hover:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-semibold rounded-lg transition-colors"
            >
              <XCircle size={14} />
              Cancel Goal
            </button>
          </div>
        )}
      </div>

      {/* Steps List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3.5">
        <div className="text-xs font-semibold text-slate-400 tracking-wider uppercase">Planned Steps</div>
        {steps.map((step) => {
          const isExpanded = !!expandedSteps[step.id]
          return (
            <div
              key={step.id}
              className={`border rounded-xl transition-all duration-200 bg-white dark:bg-slate-900 ${
                step.status === 'running'
                  ? 'border-green-500/40 dark:border-green-500/30 ring-1 ring-green-500/20'
                  : 'border-slate-200 dark:border-slate-800/80 hover:border-slate-300 dark:hover:border-slate-700'
              }`}
            >
              {/* Step Header Accordion */}
              <button
                onClick={() => toggleStepExpanded(step.id)}
                className="w-full text-left p-3.5 flex items-start gap-3 focus:outline-none"
              >
                {getStepIcon(step.status)}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-semibold text-slate-400">Step {step.step_number}</span>
                    <span className="text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 px-1.5 py-0.5 rounded font-mono font-medium flex items-center gap-1">
                      <Terminal size={10} />
                      {step.tool_name}
                    </span>
                    {step.retry_count > 0 && (
                      <span className="text-[10px] bg-amber-500/10 text-amber-500 border border-amber-500/20 px-1 py-0.2 rounded font-medium">
                        Retry {step.retry_count}
                      </span>
                    )}
                  </div>
                  <p className="text-xs font-medium text-slate-700 dark:text-slate-200 mt-1 leading-normal">
                    {step.description}
                  </p>
                </div>
                {isExpanded ? (
                  <ChevronUp size={16} className="text-slate-400 flex-shrink-0 mt-0.5" />
                ) : (
                  <ChevronDown size={16} className="text-slate-400 flex-shrink-0 mt-0.5" />
                )}
              </button>

              {/* Accordion Expandable Area */}
              {isExpanded && (
                <div className="px-3.5 pb-3.5 border-t border-slate-100 dark:border-slate-800/60 pt-3 space-y-3">
                  {/* Tool Arguments */}
                  {step.tool_params && Object.keys(step.tool_params).length > 0 && (
                    <div className="space-y-1">
                      <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Arguments</div>
                      <pre className="text-[11px] font-mono p-2.5 rounded-lg bg-slate-50 dark:bg-slate-950/50 text-slate-600 dark:text-slate-400 overflow-x-auto border border-slate-100 dark:border-slate-800/40">
                        {JSON.stringify(step.tool_params, null, 2)}
                      </pre>
                    </div>
                  )}

                  {/* Step Result */}
                  {step.result && (
                    <div className="space-y-1">
                      <div className="text-[10px] font-semibold text-green-500 uppercase tracking-wider">Output</div>
                      <pre className="text-[11px] font-mono p-2.5 rounded-lg bg-green-50/10 dark:bg-green-500/5 text-slate-600 dark:text-slate-300 overflow-x-auto border border-green-500/10 max-h-40 overflow-y-auto">
                        {typeof step.result === 'string'
                          ? step.result
                          : JSON.stringify(step.result, null, 2)}
                      </pre>
                    </div>
                  )}

                  {/* Step Error */}
                  {step.error && (
                    <div className="space-y-1">
                      <div className="text-[10px] font-semibold text-red-500 uppercase tracking-wider flex items-center gap-1">
                        <AlertCircle size={12} />
                        Error Output
                      </div>
                      <div className="text-[11px] font-mono p-2.5 rounded-lg bg-red-50/30 dark:bg-red-500/5 text-red-600 dark:text-red-400 border border-red-500/10 max-h-32 overflow-y-auto leading-relaxed">
                        {step.error}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
