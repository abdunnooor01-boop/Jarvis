import { create } from 'zustand'
import { fetchConversationDetail } from '../utils/api'
export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
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
  setCurrentConversation: (id: string) => void
  addMessage: (conversationId: string, message: Message) => void
  updateMessage: (conversationId: string, messageId: string, content: string) => void
  setMessages: (conversationId: string, messages: Message[]) => void
  setLoading: (loading: boolean) => void
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
