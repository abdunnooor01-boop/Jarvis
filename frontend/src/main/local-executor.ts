/**
 * Electron main-process Local Action Executor (Phase 15b).
 *
 * This is the process that ACTUALLY runs OS-level actions on the owner's
 * machine: shell commands, file operations and app launch. It is exposed to
 * the renderer over IPC and is deliberately separate from the backend's
 * `ToolExecutor` so that a desktop deployment can execute locally while the
 * backend keeps acting as the approval/orchestration authority.
 *
 * Safety model (defense in depth — the backend already gates approvals):
 *   1. APPROVAL GATE: an action only runs if it carries an explicitly
 *      authorized, unexpired action id (see `authorize`). Entries are
 *      single-use and expire after `APPROVAL_TTL_MS`.
 *   2. DANGEROUS-OP GUARD: destructive shell commands (sudo, rm -rf /, dd,
 *      mkfs, shutdown, fork bombs, pipe-to-shell, block-device writes, ...)
 *      and destructive file ops (delete) require an explicit `confirm` flag.
 *   3. ALLOWLIST: safe commands can be pre-approved so they run without a
 *      per-call `confirm` (but still require `authorize`).
 *   4. HOSTED-MODE BLOCKING stays enforced server-side (backend/ws.py) — the
 *      main-process executor never receives blocked tools from the backend.
 */

import { spawn } from 'child_process'
import { promises as fsp } from 'fs'
import { homedir } from 'os'
import path from 'path'

export const APPROVAL_TTL_MS = 300_000 // 300s — mirrors backend APPROVAL_TIMEOUT_SECONDS

// ---------------------------------------------------------------------------
// Types (shared contract with preload + renderer)
// ---------------------------------------------------------------------------

export type LocalTool = 'terminal' | 'file_ops' | 'app_launch'

export interface AuthorizePayload {
  /** Backend tool_call id (required, non-empty). Nothing runs without it. */
  id: string
  tool: LocalTool
  args: Record<string, unknown>
  /** Remember this approval locally (allowlist) for future calls. */
  remember?: boolean
}

export interface ExecutePayload {
  id: string
  tool: LocalTool
  args: Record<string, unknown>
  /** Explicit confirmation required for destructive ops. */
  confirm?: boolean
}

export interface LocalActionResult {
  ok: boolean
  denied?: string
  needs_confirm?: boolean
  stdout?: string
  stderr?: string
  exit_code?: number | null
  error?: string
  pid?: number
  status?: string
  path?: string
  app?: string
  name?: string
  type?: string
  content?: string
  entries?: { name: string; type: string }[]
  elapsed_ms?: number
  [key: string]: unknown
}

interface AuthorizedAction {
  tool: LocalTool
  args: Record<string, unknown>
  expiresAt: number
}

// ---------------------------------------------------------------------------
// Policy — mirrored from backend/app/tools/terminal.py + tool_policy.py
// ---------------------------------------------------------------------------

const BLOCKED_COMMANDS = [
  'rm -rf /',
  'rm -rf /*',
  'sudo ',
  'su ',
  'chmod 777 ',
  'dd if=',
  'mkfs.',
  'fdisk',
  'shutdown',
  'reboot',
  'poweroff',
  'halt',
  ':(){ :|:& };:'
]

const DANGEROUS_PATTERNS = [
  /\brm\s+-rf\s+[\/~]/,
  /\bchmod\s+777\s+/,
  /\bchown\s+\w+\s+\//,
  /\b(wget|curl)\s+.*\||\|\s*(bash|sh|python)/,
  /\beval\s+\$?\(/,
  /\bexec\s+\w+/,
  />\s*\/dev\/(sda|sdb|sdc|nvme|mmc)/,
  /\bmkfs\.\w+/,
  /\bmount\s+\//,
  /\bdd\s+if=\/dev\//,
  /\bpasswd\s+\w+/,
  /\bkillall?\s+-9\b/
]

const HIGH_RISK_COMMANDS = [
  'format',
  'fdisk',
  'mkfs',
  'dd',
  'shutdown',
  'reboot',
  'init',
  'telinit'
]

const MAX_OUTPUT_SIZE = 1_048_576 // 1 MB
const DEFAULT_TIMEOUT = 30
const MAX_COMMAND_LENGTH = 10_000

// Safe, read-only commands that run without a per-call `confirm` (still need
// `authorize`). Mirrors "read-only is safe" policy.
const DEFAULT_ALLOWLIST = [
  'ls',
  'pwd',
  'whoami',
  'date',
  'echo',
  'cat',
  'head',
  'tail',
  'ps',
  'grep',
  'git status',
  'git log',
  'git diff',
  'uname',
  'df -h',
  'free -m'
]

const IS_WIN = process.platform === 'win32'
const SHELL = IS_WIN ? 'cmd' : '/bin/bash'
const SHELL_FLAG = IS_WIN ? '/c' : '-c'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function truncate(s: string | undefined): string | undefined {
  if (!s) return s
  return s.length > MAX_OUTPUT_SIZE ? s.slice(0, MAX_OUTPUT_SIZE) + '\n... [truncated]' : s
}

function isDangerousCommand(command: string): string | null {
  const lower = command.toLowerCase().trim()
  for (const blocked of BLOCKED_COMMANDS) {
    if (lower.includes(blocked)) return `Command blocked: contains '${blocked.trim()}'`
  }
  for (const pattern of DANGEROUS_PATTERNS) {
    if (pattern.test(lower)) return `Command blocked: pattern '${pattern.source}' detected`
  }
  if (command.length > MAX_COMMAND_LENGTH) {
    return `Command too long (${command.length} chars, max ${MAX_COMMAND_LENGTH})`
  }
  return null
}

function requiresConfirmForCommand(command: string): boolean {
  const lower = command.toLowerCase()
  return HIGH_RISK_COMMANDS.some((word) => new RegExp(`\\b${word}\\b`).test(lower))
}

function isDescendant(candidate: string, parent: string): boolean {
  const rel = path.relative(path.resolve(parent), path.resolve(candidate))
  return rel === '' || (!rel.startsWith('..') && !path.isAbsolute(rel))
}

function runProc(command: string, timeout: number): Promise<LocalActionResult> {
  return new Promise<LocalActionResult>((resolve) => {
    const started = Date.now()
    const child = spawn(SHELL, [SHELL_FLAG, command], {
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: false
    })
    let stdout = ''
    let stderr = ''
    let timedOut = false

    child.stdout?.on('data', (b: Buffer) => {
      stdout = truncate((stdout + b.toString('utf8')).slice(0, MAX_OUTPUT_SIZE)) ?? ''
    })
    child.stderr?.on('data', (b: Buffer) => {
      stderr = truncate((stderr + b.toString('utf8')).slice(0, MAX_OUTPUT_SIZE)) ?? ''
    })

    const timer = setTimeout(() => {
      timedOut = true
      child.kill('SIGKILL')
    }, (timeout > 0 ? timeout : DEFAULT_TIMEOUT) * 1000)

    child.on('error', (err) => {
      clearTimeout(timer)
      resolve({ ok: false, error: `command failed to start: ${err.message}` })
    })
    child.on('close', (code) => {
      clearTimeout(timer)
      if (timedOut) {
        resolve({
          ok: false,
          denied: `command timed out after ${timeout}s`,
          stdout,
          stderr,
          exit_code: -1
        })
        return
      }
      resolve({
        ok: true,
        stdout,
        stderr,
        exit_code: code,
        status: 'complete',
        elapsed_ms: Date.now() - started
      })
    })
  })
}

// ---------------------------------------------------------------------------
// Executor
// ---------------------------------------------------------------------------

export class LocalActionExecutor {
  private authorized = new Map<string, AuthorizedAction>()
  private allowlist = new Set<string>(DEFAULT_ALLOWLIST)
  private persistAllowlist: (list: string[]) => void

  constructor(options?: { persistAllowlist?: (list: string[]) => void }) {
    this.persistAllowlist = options?.persistAllowlist ?? (() => undefined)
  }

  /** Register an owner/backend-approved action so it may execute once. */
  authorize(payload: AuthorizePayload): LocalActionResult {
    if (!payload || !payload.id || !payload.tool) {
      return { ok: false, denied: 'authorize: missing id or tool' }
    }
    if (!this.isSupportedTool(payload.tool)) {
      return { ok: false, denied: `tool '${payload.tool}' is not supported by the local executor` }
    }
    // Reject authorization outright for commands the local layer blocks entirely.
    if (payload.tool === 'terminal' && typeof payload.args?.command === 'string') {
      const danger = isDangerousCommand(payload.args.command)
      if (danger) {
        return { ok: false, denied: danger, needs_confirm: true }
      }
    }
    this.authorized.set(payload.id, {
      tool: payload.tool,
      args: payload.args ?? {},
      expiresAt: Date.now() + APPROVAL_TTL_MS
    })
    if (
      payload.remember &&
      payload.tool === 'terminal' &&
      typeof payload.args?.command === 'string'
    ) {
      this.addAllowlist(payload.args.command)
    }
    return { ok: true, status: 'authorized' }
  }

  /** Execute an authorized action. Returns the result to the renderer/chat. */
  async execute(payload: ExecutePayload): Promise<LocalActionResult> {
    if (!payload || !payload.id) {
      return { ok: false, denied: 'execute: missing action id' }
    }
    const entry = this.authorized.get(payload.id)
    if (!entry) {
      return { ok: false, denied: 'execute: action is not authorized (approve it first)' }
    }
    if (entry.expiresAt < Date.now()) {
      this.authorized.delete(payload.id)
      return { ok: false, denied: 'execute: approval expired' }
    }
    if (payload.tool !== entry.tool) {
      return { ok: false, denied: 'execute: tool does not match the authorized action' }
    }

    // Destroy the one-shot approval before running (no replay).
    this.authorized.delete(payload.id)

    const confirm = Boolean(payload.confirm)

    if (entry.tool === 'terminal' && typeof entry.args.command === 'string') {
      const command = entry.args.command
      const danger = isDangerousCommand(command)
      if (danger) return { ok: false, denied: danger, needs_confirm: true }
      const risky = requiresConfirmForCommand(command)
      const allowlisted = [...this.allowlist].some((a) => command.startsWith(a))
      if (risky && !allowlisted && !confirm) {
        return {
          ok: false,
          denied: 'terminal: destructive command requires explicit confirmation',
          needs_confirm: true
        }
      }
    }
    if (entry.tool === 'file_ops' && entry.args.operation === 'delete' && !confirm) {
      return {
        ok: false,
        denied: 'file_ops: delete requires explicit confirmation',
        needs_confirm: true
      }
    }

    try {
      switch (entry.tool) {
        case 'terminal':
          return await this.runTerminal(entry.args)
        case 'file_ops':
          return await this.runFileOps(entry.args)
        case 'app_launch':
          return await this.runAppLaunch(entry.args, confirm)
        default:
          return { ok: false, denied: `unsupported tool '${entry.tool}'` }
      }
    } catch (err) {
      return { ok: false, error: `local action failed: ${(err as Error).message}` }
    }
  }

  revoke(id: string): boolean {
    return this.authorized.delete(id)
  }

  getState(): { authorizedCount: number; allowlist: string[] } {
    const now = Date.now()
    for (const [id, entry] of this.authorized) {
      if (entry.expiresAt < now) this.authorized.delete(id)
    }
    return { authorizedCount: this.authorized.size, allowlist: [...this.allowlist] }
  }

  listAllowlist(): string[] {
    return [...this.allowlist]
  }

  addAllowlist(entry: string): boolean {
    const t = (entry ?? '').trim()
    if (!t) return false
    this.allowlist.add(t)
    this.persistAllowlist([...this.allowlist])
    return true
  }

  removeAllowlist(entry: string): boolean {
    const removed = this.allowlist.delete(entry)
    if (removed) this.persistAllowlist([...this.allowlist])
    return removed
  }

  loadAllowlist(entries: string[]): void {
    if (!Array.isArray(entries)) return
    for (const e of entries) {
      const t = (e ?? '').trim()
      if (t) this.allowlist.add(t)
    }
  }

  isSupportedTool(tool: string): tool is LocalTool {
    return tool === 'terminal' || tool === 'file_ops' || tool === 'app_launch'
  }

  // --- Tool runners ---------------------------------------------------------

  private async runTerminal(args: Record<string, unknown>): Promise<LocalActionResult> {
    const operation = String(args.operation ?? 'execute')
    const command = String(args.command ?? '').trim()
    const timeout = Number(args.timeout ?? DEFAULT_TIMEOUT)

    if (!command) return { ok: false, denied: 'terminal: empty command' }

    if (operation === 'execute') {
      return runProc(command, timeout)
    }
    if (operation === 'execute_background') {
      const child = spawn(SHELL, [SHELL_FLAG, command], { detached: true, stdio: 'ignore' })
      child.unref()
      return { ok: true, pid: child.pid ?? undefined, status: 'started' }
    }
    if (operation === 'kill') {
      const pid = Number(args.pid)
      if (!pid) return { ok: false, denied: 'terminal: pid required for kill' }
      try {
        process.kill(pid, 'SIGTERM')
        return { ok: true, pid, status: 'terminated' }
      } catch (err) {
        return { ok: false, error: `terminal: failed to kill ${pid}: ${(err as Error).message}` }
      }
    }
    return { ok: false, denied: `terminal: unknown operation '${operation}'` }
  }

  private async runFileOps(args: Record<string, unknown>): Promise<LocalActionResult> {
    const operation = String(args.operation ?? 'read')
    const rawPath = String(args.path ?? '')
    const content = String(args.content ?? '')

    if (!rawPath) return { ok: false, denied: 'file_ops: path required' }
    const resolved = path.resolve(rawPath)
    const home = homedir()

    if (!isDescendant(resolved, home) && !isDescendant(resolved, process.cwd())) {
      return {
        ok: false,
        denied: `file_ops: path '${resolved}' is outside the allowed workspace`
      }
    }

    switch (operation) {
      case 'read': {
        try {
          const data = await fsp.readFile(resolved, 'utf8')
          const stat = await fsp.stat(resolved)
          return { ok: true, content: truncate(data), status: 'read', path: resolved, type: stat.isDirectory() ? 'dir' : 'file' }
        } catch (err) {
          return { ok: false, error: `file_ops: read failed: ${(err as Error).message}` }
        }
      }
      case 'write': {
        try {
          await fsp.mkdir(path.dirname(resolved), { recursive: true })
          await fsp.writeFile(resolved, content, 'utf8')
          return { ok: true, status: 'written', path: resolved }
        } catch (err) {
          return { ok: false, error: `file_ops: write failed: ${(err as Error).message}` }
        }
      }
      case 'list': {
        try {
          const names = await fsp.readdir(resolved)
          const entries: { name: string; type: string }[] = []
          for (const name of names) {
            const st = await fsp.stat(path.join(resolved, name)).catch(() => null)
            entries.push({ name, type: st?.isDirectory() ? 'dir' : st?.isSymbolicLink() ? 'link' : 'file' })
          }
          return { ok: true, entries, status: 'listed', path: resolved }
        } catch (err) {
          return { ok: false, error: `file_ops: list failed: ${(err as Error).message}` }
        }
      }
      case 'delete': {
        try {
          await fsp.unlink(resolved)
          return { ok: true, status: 'deleted', path: resolved }
        } catch (err) {
          return { ok: false, error: `file_ops: delete failed: ${(err as Error).message}` }
        }
      }
      default:
        return { ok: false, denied: `file_ops: unknown operation '${operation}'` }
    }
  }

  private async runAppLaunch(
    args: Record<string, unknown>,
    confirm: boolean
  ): Promise<LocalActionResult> {
    const operation = String(args.action ?? 'open_app')

    if (operation === 'list_running') {
      return runProc(IS_WIN ? 'tasklist' : 'ps -e', 10)
    }

    const name = String(args.name ?? args.app ?? '').trim()
    if (!name) return { ok: false, denied: 'app_launch: app name/path required' }

    if (operation === 'open_app') {
      try {
        const child = spawn(name, { detached: true, stdio: 'ignore', shell: false })
        child.unref()
        return { ok: true, pid: child.pid ?? undefined, status: 'launched', app: name }
      } catch (err) {
        return { ok: false, error: `app_launch: failed to launch '${name}': ${(err as Error).message}` }
      }
    }
    if (operation === 'close_app') {
      if (!confirm) {
        return { ok: false, denied: 'app_launch: closing an app requires explicit confirmation', needs_confirm: true }
      }
      return runProc(IS_WIN ? `taskkill /IM ${name} /F` : `pkill -f "${name}"`, 10)
    }
    return { ok: false, denied: `app_launch: unknown operation '${operation}'` }
  }
}
