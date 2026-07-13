import React from 'react'
import {
  X,
  Play,
  Calendar,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  ExternalLink,
  Layers,
  Image as ImageIcon
} from 'lucide-react'
import { TestRun, TestStepResult } from '../stores/testing'

interface TestRunDetailProps {
  run: TestRun
  onClose: () => void
  onTriggerPlan?: (planId: string) => void
  isTriggering?: boolean
}

export const TestRunDetail: React.FC<TestRunDetailProps> = ({
  run,
  onClose,
  onTriggerPlan,
  isTriggering = false
}) => {
  const formatDate = (isoStr: string) => {
    try {
      return new Date(isoStr).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      })
    } catch {
      return isoStr
    }
  }

  const formatDuration = (sec: number) => {
    if (sec < 60) return `${sec}s`
    const mins = Math.floor(sec / 60)
    const secs = sec % 60
    return `${mins}m ${secs}s`
  }

  const getStatusIcon = (status: TestRun['status']) => {
    switch (status) {
      case 'passed':
        return <CheckCircle className="text-green-500 w-8 h-8" />
      case 'failed':
        return <XCircle className="text-red-500 w-8 h-8" />
      case 'running':
        return <AlertCircle className="text-amber-500 w-8 h-8 animate-pulse" />
      default:
        return <AlertCircle className="text-slate-400 w-8 h-8" />
    }
  }

  return (
    <div className="flex flex-col h-full bg-slate-50 dark:bg-slate-950/40 p-6 overflow-y-auto max-h-full">
      {/* Header */}
      <div className="flex items-start justify-between pb-5 border-b border-slate-200 dark:border-slate-800">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold px-2 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 rounded-md uppercase tracking-wider">
              Run #{run.id.slice(-6).toUpperCase()}
            </span>
            <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${
              run.status === 'passed'
                ? 'bg-green-500/10 text-green-500 border-green-500/20'
                : run.status === 'failed'
                ? 'bg-red-500/10 text-red-500 border-red-500/20'
                : 'bg-amber-500/10 text-amber-500 border-amber-500/20'
            }`}>
              {run.status.toUpperCase()}
            </span>
          </div>
          <h3 className="text-xl font-bold text-slate-950 dark:text-white flex items-center gap-1.5">
            {run.plan_url}
            <a
              href={run.plan_url}
              target="_blank"
              rel="noreferrer"
              className="text-slate-400 hover:text-indigo-500 transition-colors"
            >
              <ExternalLink size={16} />
            </a>
          </h3>
        </div>
        
        <div className="flex items-center gap-2">
          {onTriggerPlan && (
            <button
              onClick={() => onTriggerPlan(run.plan_id)}
              disabled={isTriggering || run.status === 'running'}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 disabled:dark:bg-slate-800 text-white rounded-lg text-sm font-medium transition-colors"
            >
              <Play size={14} />
              {isTriggering ? 'Running...' : 'Run Again'}
            </button>
          )}
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg text-slate-400 hover:text-slate-600 transition-colors"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {/* Summary Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 my-6">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 rounded-xl flex items-center gap-3">
          <div className="p-3 bg-indigo-500/10 text-indigo-500 rounded-lg">
            <Layers size={18} />
          </div>
          <div>
            <p className="text-xs text-slate-500">Test Steps</p>
            <p className="text-lg font-bold text-slate-850 dark:text-white">
              {(run.passed_count || 0) + (run.failed_count || 0)}
            </p>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 rounded-xl flex items-center gap-3">
          <div className="p-3 bg-green-500/10 text-green-500 rounded-lg">
            <CheckCircle size={18} />
          </div>
          <div>
            <p className="text-xs text-slate-500">Passed</p>
            <p className="text-lg font-bold text-green-500">{run.passed_count}</p>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 rounded-xl flex items-center gap-3">
          <div className="p-3 bg-red-500/10 text-red-500 rounded-lg">
            <XCircle size={18} />
          </div>
          <div>
            <p className="text-xs text-slate-500">Failed</p>
            <p className="text-lg font-bold text-red-500">{run.failed_count}</p>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 rounded-xl flex items-center gap-3">
          <div className="p-3 bg-amber-500/10 text-amber-500 rounded-lg">
            <Clock size={18} />
          </div>
          <div>
            <p className="text-xs text-slate-500">Duration</p>
            <p className="text-lg font-bold text-slate-850 dark:text-white">{formatDuration(run.duration)}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Step Assertions details */}
        <div className="lg:col-span-2 space-y-4">
          <h4 className="text-sm font-semibold uppercase text-slate-400 tracking-wider flex items-center gap-2">
            Execution Steps & Assertions
          </h4>
          
          <div className="space-y-2.5">
            {run.results && run.results.length > 0 ? (
              run.results.map((step, index) => (
                <div
                  key={step.id || index}
                  className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 transition-all"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5">
                        {step.status === 'passed' ? (
                          <CheckCircle className="text-green-500 w-5 h-5 flex-shrink-0" />
                        ) : step.status === 'failed' ? (
                          <XCircle className="text-red-500 w-5 h-5 flex-shrink-0" />
                        ) : (
                          <AlertCircle className="text-slate-400 w-5 h-5 flex-shrink-0" />
                        )}
                      </div>
                      <div className="space-y-0.5">
                        <p className="text-sm font-medium text-slate-900 dark:text-white leading-snug">
                          {step.name}
                        </p>
                        {step.duration && (
                          <p className="text-xs text-slate-400 font-mono">
                            Duration: {step.duration}s
                          </p>
                        )}
                      </div>
                    </div>
                  </div>

                  {step.status === 'failed' && step.error && (
                    <div className="mt-3 pl-8">
                      <div className="bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/40 rounded-lg p-3 text-xs text-red-600 dark:text-red-400 font-mono whitespace-pre-wrap leading-relaxed">
                        <p className="font-bold mb-1">Execution Failure Error:</p>
                        {step.error}
                      </div>
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="text-center py-8 text-sm text-slate-400 bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 rounded-xl">
                No step details recorded for this run.
              </div>
            )}
          </div>
        </div>

        {/* Visual Screenshot Gallery */}
        <div className="space-y-4">
          <h4 className="text-sm font-semibold uppercase text-slate-400 tracking-wider flex items-center gap-2">
            <ImageIcon size={14} /> Captured Screenshots
          </h4>

          {run.screenshots && run.screenshots.length > 0 ? (
            <div className="grid grid-cols-1 gap-3">
              {run.screenshots.map((src, idx) => (
                <div key={idx} className="group relative bg-slate-100 dark:bg-slate-900 rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 aspect-video shadow-sm">
                  <img
                    src={src}
                    alt={`Screenshot ${idx + 1}`}
                    className="w-full h-full object-cover transition-transform group-hover:scale-[1.03]"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent flex items-end p-3 opacity-0 group-hover:opacity-100 transition-opacity">
                    <span className="text-white text-xs font-medium">Screenshot #{idx + 1}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-slate-400 bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 rounded-xl aspect-square">
              <ImageIcon size={32} className="text-slate-300 mb-2" />
              <span className="text-xs font-medium">No screenshots captured</span>
            </div>
          )}

          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 rounded-xl space-y-2">
            <h5 className="text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">
              Execution Details
            </h5>
            <div className="space-y-1.5 text-xs text-slate-500">
              <div className="flex justify-between">
                <span>Date & Time</span>
                <span className="font-medium text-slate-800 dark:text-slate-200">
                  {formatDate(run.created_at)}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Engine Version</span>
                <span className="font-medium text-slate-850 dark:text-white">v1.4 (Chromium Headless)</span>
              </div>
              <div className="flex justify-between">
                <span>Total Assertions</span>
                <span className="font-medium text-slate-850 dark:text-white">
                  {(run.passed_count || 0) + (run.failed_count || 0)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
