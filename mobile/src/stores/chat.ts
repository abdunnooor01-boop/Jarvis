import { create } from 'zustand';
import api from '../services/api';
import wsService from '../services/websocket';
import { Conversation, ConversationDetail, Message } from '../types/api';

interface ChatState {
  conversations: Conversation[];
  currentConversationId: string | null;
  messages: Record<string, Message[]>;
  isLoading: boolean;
  isStreaming: boolean;
  error: string | null;
  loadConversations: () => Promise<void>;
  selectConversation: (id: string) => Promise<void>;
  createConversation: (title?: string) => Promise<string | null>;
  deleteConversation: (id: string) => Promise<void>;
  sendMessage: (content: string) => void;
  addMessage: (conversationId: string, message: Message) => void;
  setLoading: (loading: boolean) => void;
  setStreaming: (streaming: boolean) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  currentConversationId: null,
  messages: {},
  isLoading: false,
  isStreaming: false,
  error: null,

  loadConversations: async () => {
    try {
      const conversations = await api.listConversations();
      set({ conversations });
    } catch (err: any) {
      set({ error: err.detail || 'Failed to load conversations' });
    }
  },

  selectConversation: async (id: string) => {
    set({ currentConversationId: id, isLoading: true });
    try {
      const detail = await api.getConversation(id);
      set((state) => ({
        messages: { ...state.messages, [id]: detail.messages },
        isLoading: false,
      }));
    } catch (err: any) {
      set({ error: err.detail || 'Failed to load conversation', isLoading: false });
    }
  },

  createConversation: async (title?: string) => {
    try {
      const conv = await api.createConversation({ title });
      set((state) => ({
        conversations: [conv, ...state.conversations],
        currentConversationId: conv.id,
      }));
      return conv.id;
    } catch (err: any) {
      set({ error: err.detail || 'Failed to create conversation' });
      return null;
    }
  },

  deleteConversation: async (id: string) => {
    try {
      await api.deleteConversation(id);
      set((state) => ({
        conversations: state.conversations.filter((c) => c.id !== id),
        currentConversationId:
          state.currentConversationId === id ? null : state.currentConversationId,
      }));
    } catch (err: any) {
      set({ error: err.detail || 'Failed to delete conversation' });
    }
  },

  sendMessage: (content: string) => {
    const { currentConversationId } = get();
    if (!currentConversationId) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };

    set((state) => ({
      messages: {
        ...state.messages,
        [currentConversationId]: [
          ...(state.messages[currentConversationId] || []),
          userMessage,
        ],
      },
      isStreaming: true,
    }));

    wsService.sendMessage(currentConversationId, content);
  },

  addMessage: (conversationId: string, message: Message) => {
    set((state) => ({
      messages: {
        ...state.messages,
        [conversationId]: [...(state.messages[conversationId] || []), message],
      },
      isStreaming: false,
      isLoading: false,
    }));
  },

  setLoading: (loading: boolean) => set({ isLoading: loading }),
  setStreaming: (streaming: boolean) => set({ isStreaming: streaming }),
}));