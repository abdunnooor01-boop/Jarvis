import { create } from 'zustand'

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
  setConversations: (conversations: Conversation[]) => void
  setCurrentConversation: (id: string) => void
  addMessage: (conversationId: string, message: Message) => void
  updateMessage: (conversationId: string, messageId: string, content: string) => void
  setMessages: (conversationId: string, messages: Message[]) => void
  setLoading: (loading: boolean) => void
}

export const useChatStore = create<ChatState>((set) => ({
  conversations: [],
  currentConversationId: null,
  messages: {},
  isLoading: false,
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
  setLoading: (loading) => set({ isLoading: loading })
}))
