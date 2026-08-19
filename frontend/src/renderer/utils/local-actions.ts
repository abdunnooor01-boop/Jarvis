/**
 * Renderer-side client for the Phase 15b local action executor.
 *
 * Bridges an owner-approved tool call to the Electron main-process executor
 * over IPC so the action actually runs on the owner's machine and the result
 * comes back into the chat loop.
 *
 * Flow (full end-to-end is wired by 15c approval UI):
 *   backend WS sends `tool_proposal` → owner approves → (15c sends
 *   `tool_decision: approve`) → renderer calls `executeApprovedLocalAction`
 *   here → main-process `LocalActionExecutor` runs shell/file/app locally →
 *   the returned result is appended back into the chat / WS loop.
 *
 * In hosted (web) mode `window.api.localExecutor` is absent (web-api-shim
 * leaves it undefined), so this always returns `unavailable` — mirroring the
 * backend's hosted-mode blocking without relying on it alone.
 */

import type {
  AuthorizePayload,
  ExecutePayload,
  LocalActionResult,
  LocalTool
} from '../../main/local-executor'

export interface ProxyActionInput {
  id: string
  tool: LocalTool
  args: Record<string, unknown>
  confirm?: boolean
  remember?: boolean
}

export function isLocalExecutorAvailable(): boolean {
  return Boolean(
    typeof window !== 'undefined' &&
      (window as any).api?.localExecutor &&
      typeof (window as any).api.localExecutor.execute === 'function'
  )
}

/** Run an approved local action through the main-process executor. */
export async function executeApprovedLocalAction(
  input: ProxyActionInput
): Promise<LocalActionResult> {
  if (!isLocalExecutorAvailable()) {
    return { ok: false, denied: 'local executor unavailable (hosted/web mode)' }
  }
  const exec = (window as any).api.localExecutor

  // Register the backend/owner-approved action id so the main process will run
  // it exactly once (authorize → execute).
  const authorizePayload: AuthorizePayload = {
    id: input.id,
    tool: input.tool,
    args: input.args,
    ...(input.remember ? { remember: true } : {})
  }
  const auth = await exec.authorize(authorizePayload)
  if (!auth?.ok) {
    return { ok: false, denied: auth?.denied ?? 'local action could not be authorized' }
  }

  const executePayload: ExecutePayload = {
    id: input.id,
    tool: input.tool,
    args: input.args,
    ...(input.confirm ? { confirm: true } : {})
  }
  return (await exec.execute(executePayload)) as LocalActionResult
}

/** True when a result indicates a destructive op needs explicit confirm. */
export function needsConfirmation(result: LocalActionResult | undefined | null): boolean {
  return Boolean(result && !result.ok && result.needs_confirm)
}
