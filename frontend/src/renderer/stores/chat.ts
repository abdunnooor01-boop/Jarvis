import { create } from 'zustand'
import { fetchConversationDetail } from '../utils/api'

/**
 * Lifecycle of a tool action entry in the conversation (Phase 15c):
 *   `tool_call` arrives → status 'requested' (optimistic, no proposal yet)
 *   `tool_proposal` (needs approval) → status 'pending' + proposalId
 *   owner approves (desktop) → 'executing' (local run) until `tool_result`
 *   `tool_result` → 'executed' | 'denied' | 'unavailable'
 */
export type ToolActionStatus =
  | 'requested' // tool_call emitted; no proposal yet (auto-approved or awaiting)
  | 'pending' // tool_proposal — approval card shown
  | 'executing' // owner approved; local executor running / waiting on backend
  | 'executed' // backend tool_result arrived (approved path)
  | 'denied' // denied by owner or timed out
  | 'unavailable' // hosted-blocked: backend returned unavailable

export interface ToolActionInfo {
  /** Backend proposal id — required to send a tool_decision. */
  proposalId?: string
  /** Backend tool_call id — stable key for the entry. */
  toolCallId: string
  toolName: string
  arguments: Record<string, unknown>
  reason?: string
  status: ToolActionStatus
  /** 'approve' | 'deny' chosen by the owner (if any). */
  decision?: 'approve' | 'deny'
  /** Approval was marked "always allow this tool". */
  remember?: boolean
  /** Backend `approval` reason on the result frame. */
  approval?: string
  /** Backend tool_result payload (authoritative outcome). */
  result?: unknown
  /** Outcome of the local (Electron) execution, when available. */
  localResult?: { ok: boolean; denied?: string; needs_confirm?: boolean; error?: string; [k: string]: unknown }
  timestamp: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  /** When set, this message renders as an action-log entry / approval card. */
  kind?: 'action'
  action?: ToolActionInfo
}
export interface Conversation {
  id: string
  title: string
}
interface ChatState {
  conversations: Conversation[]
  currentConversationId: string | null
  messages: Record<string, Message[]>
  isLoading: boolean
  /** True while a conversation's history is being fetched from the backend. */
  historyLoading: boolean
  setConversations: (conversations: Conversation[]) => void
  setCurrentConversation: (id: string | null) => void
  addMessage: (conversationId: string, message: Message) => void
  updateMessage: (conversationId: string, messageId: string, content: string) => void
  setMessages: (conversationId: string, messages: Message[]) => void
  setLoading: (loading: boolean) => void
  /** Add a tool-action entry (deduped by toolCallId). */
  addAction: (conversationId: string, action: ToolActionInfo) => void
  /** Patch an existing tool-action entry in-place. */
  updateAction: (conversationId: string, toolCallId: string, patch: Partial<ToolActionInfo>) => void
  /** Fetch and store the message history for a conversation (idempotent). */
  loadHistory: (conversationId: string, token: string) => Promise<void>
}
export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  currentConversationId: null,
  messages: {},
  isLoading: false,
  historyLoading: false,
  setConversations: (conversations) => set({ conversations }),
  setCurrentConversation: (id) => set({ currentConversationId: id }),
  addMessage: (conversationId, message) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [conversationId]: [...(state.messages[conversationId] || []), message]
      }
    })),
  updateMessage: (conversationId, messageId, content) =>
    set((state) => {
      const list = state.messages[conversationId]
      if (!list) return state
      const idx = list.findIndex((m) => m.id === messageId)
      if (idx === -1) return state
      const next = [...list]
      next[idx] = { ...next[idx], content }
      return { messages: { ...state.messages, [conversationId]: next } }
    }),
  setMessages: (conversationId, messages) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [conversationId]: messages
      }
    })),
  setLoading: (loading) => set({ isLoading: loading }),
  addAction: (conversationId, action) =>
    set((state) => {
      const list = state.messages[conversationId] || []
      const existing = list.find(
        (m) => m.kind === 'action' && m.action?.toolCallId === action.toolCallId
      )
      if (existing && existing.action) {
        const next = list.map((m) =>
          m.id === existing.id
            ? { ...m, action: { ...existing.action!, ...action } }
            : m
        )
        return { messages: { ...state.messages, [conversationId]: next } }
      }
      const entryMessage: Message = {
        id: `action-${action.toolCallId}`,
        role: 'system',
        kind: 'action',
        content: '',
        timestamp: action.timestamp,
        action
      }
      return {
        messages: { ...state.messages, [conversationId]: [...list, entryMessage] }
      }
    }),
  updateAction: (conversationId, toolCallId, patch) =>
    set((state) => {
      const list = state.messages[conversationId]
      if (!list) return state
      const idx = list.findIndex((m) => m.kind === 'action' && m.action?.toolCallId === toolCallId)
      if (idx === -1) return state
      const next = [...list]
      const existing = next[idx]
      next[idx] = {
        ...existing,
        action: { ...existing.action!, ...patch }
      }
      return { messages: { ...state.messages, [conversationId]: next } }
    }),
  loadHistory: async (conversationId, token) => {
    const state = get()
    // Already loaded (or has live/streaming messages) — never clobber the
    // in-session state with a server snapshot (could race mid-stream).
    if (state.messages[conversationId] !== undefined) return
    set({ historyLoading: true })
    try {
      const detail = await fetchConversationDetail(conversationId, token)
      set((s) => ({
        messages: {
          ...s.messages,
          [conversationId]: detail.messages.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            timestamp: m.created_at
          }))
        },
        historyLoading: false
      }))
    } catch {
      // Non-fatal — the conversation simply starts empty if the fetch fails.
      set({ historyLoading: false })
    }
  }
}))