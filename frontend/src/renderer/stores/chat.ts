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
  setMessages: (conversationId, messages) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [conversationId]: messages
      }
    })),
  setLoading: (loading) => set({ isLoading: loading })
}))
