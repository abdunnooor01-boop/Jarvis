/**
 * Phase 15c — in-chat approval card + action log entry.
 *
 * Renders one tool action proposed by the backend (WS `tool_proposal`) as a
 * card the owner can Approve / Deny (with an "always allow this tool"
 * option), then shows the outcome (local execution result + backend
 * `tool_result`) inline in the conversation.
 *
 * Desktop contract (15b): approve sends `tool_decision {approve}` to the
 * backend (which continues its loop / streams `tool_result`), AND — when the
 * Electron local executor is available — runs the action via
 * `executeApprovedLocalAction` so it really executes on the owner's machine.
 * `confirm` is a TOP-LEVEL execute() field (not inside args). Destructive
 * ops that come back `needs_confirm` are re-confirmed inline before running.
 */

import React, { useState } from 'react'
import {
  Terminal,
  FileText,
  AppWindow,
  AlertTriangle,
  XCircle,
  CheckCircle2,
  Loader2,
  Ban,
  HardDrive,
  Zap,
} from 'lucide-react'
import type { ToolActionInfo } from '../stores/chat'
import { useChatStore } from '../stores/chat'
import { useAuthStore } from '../stores/auth'
import {
  executeApprovedLocalAction,
  isLocalExecutorAvailable,
  needsConfirmation,
} from '../utils/local-actions'
import { addToolAllowlist } from '../utils/api'
import type { LocalTool } from '../../main/local-executor'
import type { SendToolDecision } from '../hooks/useWebSocket'

// Backend tool names → the Electron local executor tool types (15b).
const LOCAL_TOOL_MAP: Record<string, LocalTool> = {
  terminal: 'terminal',
  file_ops: 'file_ops',
  app_launch: 'app_launch',
}

function humanName(toolName: string): string {
  const map: Record<string, string> = {
    terminal: 'Terminal',
    file_ops: 'Files',
    app_launch: 'Apps',
  }
  if (map[toolName]) return map[toolName]
  return toolName
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function toolIcon(toolName: string) {
  if (toolName === 'terminal') return <Terminal size={14} />
  if (toolName === 'file_ops') return <FileText size={14} />
  if (toolName === 'app_launch') return <AppWindow size={14} />
  return <Zap size={14} />
}

/** One-line human summary of the action for compact entries. */
function summarize(action: ToolActionInfo): string {
  const args = action.arguments || {}
  if (action.toolName === 'terminal') return String(args.command ?? '')
  if (action.toolName === 'file_ops') {
    return `${String(args.operation ?? 'read')} ${String(args.path ?? '')}`.trim()
  }
  if (action.toolName === 'app_launch') {
    return `${String(args.action ?? 'open_app')} ${String(args.name ?? args.app ?? '')}`.trim()
  }
  return Object.entries(args)
    .map(([k, v]) => `${k}=${String(v)}`)
    .join(' ')
}

/** Multi-line argument preview for the card body. */
function formatArgs(args: Record<string, unknown>): string {
  const entries = Object.entries(args ?? {})
  if (entries.length === 0) return '(no arguments)'
  return entries
    .map(([k, v]) => {
      const value = typeof v === 'string' ? v : JSON.stringify(v)
      return `${k}: ${value.length > 140 ? value.slice(0, 137) + '…' : value}`
    })
    .join('\n')
}

function resultSummary(result: unknown): string {
  if (result == null) return ''
  const r = result as Record<string, unknown>
  if (r.stdout && typeof r.stdout === 'string') {
    const s = String(r.stdout).trim()
    if (s) return s.length > 200 ? s.slice(0, 197) + '…' : s
  }
  if (typeof r.status === 'string') return String(r.status)
  if (r.error) return String(r.error)
  if (r.denied) return String(r.denied ?? 'denied')
  const json = JSON.stringify(r)
  return json.length > 200 ? json.slice(0, 197) + '…' : json
}

interface ApprovalCardProps {
  conversationId: string
  action: ToolActionInfo
  sendToolDecision: SendToolDecision
}

type LocalPhase = 'idle' | 'running' | 'confirm-needed' | 'done'

export const ApprovalCard: React.FC<ApprovalCardProps> = ({
  conversationId,
  action,
  sendToolDecision,
}) => {
  const token = useAuthStore((s) => s.token)
  const updateAction = useChatStore((s) => s.updateAction)
  const [remember, setRemember] = useState(false)
  const [localPhase, setLocalPhase] = useState<LocalPhase>('idle')
  const [localError, setLocalError] = useState<string | null>(null)
  const localAvailable = isLocalExecutorAvailable()
  const localTool = LOCAL_TOOL_MAP[action.toolName]
  const status = action.status

  const patch = (p: Partial<ToolActionInfo>) => {
    updateAction(conversationId, action.toolCallId, p)
  }

  /** Send the decision so the backend loop can continue (idempotent per id). */
  const dispatchDecision = (decision: 'approve' | 'deny') => {
    if (!action.proposalId) return
    sendToolDecision({
      proposalId: action.proposalId,
      decision,
      ...(decision === 'approve' && remember ? { remember: true } : {}),
    })
  }

  /** Run the approved action through the 15b local executor (desktop only). */
  const runLocal = async (confirm: boolean) => {
    if (!localTool) {
      // Backend handles tools the local executor doesn't support.
      setLocalPhase('done')
      return
    }
    setLocalPhase('running')
    setLocalError(null)
    try {
      const result = await executeApprovedLocalAction({
        id: action.toolCallId,
        tool: localTool,
        args: action.arguments ?? {},
        ...(confirm ? { confirm: true } : {}),
        ...(remember ? { remember: true } : {}),
      })
      if (needsConfirmation(result)) {
        // Destructive op — require an explicit second confirmation.
        setLocalPhase('confirm-needed')
      } else {
        setLocalPhase('done')
        if (result && !result.ok && result.denied) setLocalError(String(result.denied))
      }
      patch({
        localResult: (result ?? { ok: false, denied: 'no local result' }) as Partial<ToolActionInfo>['localResult'],
      })
    } catch (err) {
      setLocalPhase('done')
      setLocalError(err instanceof Error ? err.message : 'local execution failed')
    }
  }

  const handleApprove = () => {
    dispatchDecision('approve')
    patch({ status: 'executing', decision: 'approve', remember })
    // "Always allow this tool" is persisted via the backend allowlist API,
    // matching ANY future call of this tool (arguments: null).
    if (remember && token) {
      addToolAllowlist(token, action.toolName).catch(() => {
        /* non-fatal — approval still sent */
      })
    }
    void runLocal(false)
  }

  const handleConfirmDestructive = () => {
    setLocalPhase('running')
    void runLocal(true)
  }

  const handleDeny = () => {
    dispatchDecision('deny')
    patch({ status: 'denied', decision: 'deny' })
  }

  // ---- Resolved states: compact action-log entry ---------------------------
  if (status === 'executed' || status === 'denied' || status === 'unavailable') {
    const isOk = status === 'executed'
    const isUnavail = status === 'unavailable'
    const local = action.localResult
    return (
      <div className="flex justify-start animate-fade-in">
        <div className="max-w-[85%] w-full min-w-0 rounded-xl border border-slate-800 bg-slate-900/50 px-3 py-2">
          <div className="flex items-center gap-2 text-xs">
            <span
              className={`flex items-center gap-1 px-1.5 py-0.5 rounded-md ${
                isOk
                  ? 'text-emerald-400 bg-emerald-950/40'
                  : isUnavail
                    ? 'text-amber-400 bg-amber-950/40'
                    : 'text-red-400 bg-red-950/40'
              }`}
            >
              {isOk ? (
                <CheckCircle2 size={12} />
              ) : isUnavail ? (
                <Ban size={12} />
              ) : (
                <XCircle size={12} />
              )}
              {isOk ? 'Completed' : isUnavail ? 'Unavailable' : 'Denied'}
            </span>
            <span className="text-slate-400">{humanName(action.toolName)}</span>
            <span className="text-slate-600 truncate font-mono">{summarize(action)}</span>
          </div>
          <details className="mt-1.5 group">
            <summary className="text-[10px] text-slate-600 cursor-pointer hover:text-slate-400 select-none">
              Details
            </summary>
            <div className="mt-1.5 space-y-1.5">
              {local && (
                <p className="text-[11px] text-indigo-300/80">
                  Local:{' '}
                  {String(local.ok ? local.status ?? 'ok' : local.denied ?? local.error ?? 'failed')}
                </p>
              )}
              <pre className="text-[11px] text-slate-400 font-mono whitespace-pre-wrap break-words bg-black/30 rounded-lg p-2 max-h-40 overflow-auto">
                {resultSummary(action.result)}
              </pre>
            </div>
          </details>
        </div>
      </div>
    )
  }

  // ---- Running / confirm-needed: mid-flight visual -------------------------
  if (status === 'executing' || localPhase === 'running' || localPhase === 'confirm-needed') {
    const awaitingLocal = status === 'executing' && localPhase === 'confirm-needed'
    return (
      <div className="flex justify-start animate-fade-in">
        <div className="max-w-[85%] w-full min-w-0 rounded-xl border border-indigo-500/25 bg-slate-900/70 px-3 py-2">
          <div className="flex items-center gap-2 text-xs">
            <Loader2 size={12} className="animate-spin text-indigo-400" />
            <span className="text-indigo-300">{humanName(action.toolName)}</span>
            <span className="text-slate-500 truncate font-mono">{summarize(action)}</span>
          </div>
          {awaitingLocal ? (
            <div className="mt-2 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-950/30 px-3 py-2">
              <AlertTriangle size={14} className="text-red-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-red-300 font-medium">
                  Destructive action — explicit confirmation required
                </p>
                <p className="text-[11px] text-red-400/80 mt-0.5">
                  {action.localResult?.denied ?? 'This operation is irreversible.'}
                </p>
                <div className="flex items-center gap-2 mt-2">
                  <button
                    onClick={handleConfirmDestructive}
                    className="rounded-lg bg-red-600 hover:bg-red-500 px-3 py-1.5 text-xs font-semibold text-white transition-colors"
                  >
                    Confirm & run
                  </button>
                  <button
                    onClick={() => setLocalPhase('done')}
                    className="rounded-lg px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
                  >
                    Skip local
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-[11px] text-slate-500 mt-1">Executing…</p>
          )}
        </div>
      </div>
    )
  }

  // ---- Pending: the approval card ------------------------------------------
  return (
    <div className="flex justify-start animate-fade-in">
      <div className="max-w-[85%] w-full min-w-0 rounded-2xl border border-indigo-500/30 bg-slate-900/80 shadow-lg shadow-indigo-950/30 px-4 py-3">
        {/* Header */}
        <div className="flex items-center gap-2">
          <span className="flex items-center justify-center w-7 h-7 rounded-lg bg-indigo-500/15 text-indigo-300">
            {toolIcon(action.toolName)}
          </span>
          <span className="text-xs font-semibold text-slate-200">{humanName(action.toolName)}</span>
          <span className="ml-auto flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-300">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
            Requires approval
          </span>
        </div>

        {/* Args preview */}
        <pre className="mt-2.5 text-[11px] leading-relaxed font-mono text-slate-300 whitespace-pre-wrap break-words bg-black/40 border border-slate-800 rounded-xl p-3 max-h-44 overflow-auto">
          {formatArgs(action.arguments ?? {})}
        </pre>

        {/* Scope / execution context */}
        <div className="mt-2.5 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
          <span className="flex items-center gap-1">
            <HardDrive size={11} className="text-slate-600" />
            {localAvailable && localTool
              ? 'Executes on this device'
              : 'Hosted — action unavailable here'}
          </span>
          {action.reason && <span className="text-slate-600">· {action.reason}</span>}
          {localError && (
            <span className="flex items-center gap-1 text-amber-400/90">· {localError}</span>
          )}
        </div>

        {/* Always allow */}
        <label className="mt-2.5 flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
            className="w-3.5 h-3.5 rounded border-slate-600 bg-slate-800 accent-indigo-500"
          />
          <span className="text-[11px] text-slate-400">Always allow this tool from now on</span>
        </label>

        {/* Actions */}
        <div className="mt-3 flex items-center gap-2">
          <button
            onClick={handleApprove}
            className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 px-4 py-2 text-xs font-semibold text-white transition-colors"
          >
            <CheckCircle2 size={14} />
            Approve
          </button>
          <button
            onClick={handleDeny}
            className="flex-1 flex items-center justify-center gap-1.5 rounded-lg border border-slate-700 hover:border-red-500/50 hover:text-red-300 px-4 py-2 text-xs font-medium text-slate-300 transition-colors"
          >
            <XCircle size={14} />
            Deny
          </button>
        </div>
      </div>
    </div>
  )
}

export default ApprovalCard