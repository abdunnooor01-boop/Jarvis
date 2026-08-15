import { useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '../stores/auth'
import { useChatStore, Message } from '../stores/chat'
import { useMemoryStore } from '../stores/memory'
import { useTaskStore } from '../stores/tasks'

function getWsUrl(): string {
  // Allow override via env var
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL
  }
  // In browser builds, derive from the current page origin
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}/ws/v1/chat`
  }
  // Fallback for SSR / non-browser
  return 'ws://localhost:8000/ws/v1/chat'
}

const WS_URL = getWsUrl()

export const useWebSocket = () => {
  const { token } = useAuthStore()
  const { currentConversationId, setCurrentConversation, addMessage, updateMessage, setLoading } = useChatStore()
  const { setRecalling, addMemoryContext } = useMemoryStore()
  const ws = useRef<WebSocket | null>(null)
  const reconnectTimeout = useRef<NodeJS.Timeout>()
  // Map conversationId → id of the in-progress assistant message being streamed
  const streamingMsgIdsRef = useRef<Map<string, string>>(new Map())
  // Ref to track the active conversation ID independently of the store (avoids
  // closure staleness when streaming begins before conversation_created sets it)
  const activeConvIdRef = useRef<string | null>(null)
  // Accumulate chunks that arrive before we know the conversation_id
  const pendingChunksRef = useRef<string>('')

  const connect = useCallback(() => {
    if (!token) return

    // Sync ref from store on every connect
    activeConvIdRef.current = currentConversationId

    ws.current = new WebSocket(WS_URL)

    ws.current.onopen = () => {
      console.log('WS Connected')
      // Send auth token
      ws.current?.send(JSON.stringify({ type: 'auth', token }))
    }

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === 'chunk') {
        // LIVE streaming — append each chunk to the in-progress assistant
        // message so the UI renders text as it arrives.
        const convId = data.conversation_id || activeConvIdRef.current
        const content = data.content || ''
        if (!convId) {
          // No conversation ID yet (first message) — buffer temporarily
          pendingChunksRef.current += content
          return
        }
        const msgId = streamingMsgIdsRef.current.get(convId)
        if (msgId) {
          const list = useChatStore.getState().messages[convId] || []
          const existing = list.find((m) => m.id === msgId)?.content || ''
          updateMessage(convId, msgId, existing + content)
        } else {
          const assistantMessage: Message = {
            id: `streaming-${convId}-${Date.now()}`,
            role: 'assistant',
            content,
            timestamp: new Date().toISOString()
          }
          addMessage(convId, assistantMessage)
          streamingMsgIdsRef.current.set(convId, assistantMessage.id)
        }
      } else if (data.type === 'done') {
        // Streaming complete — message stays with full content; stop tracking
        const convId = data.conversation_id || activeConvIdRef.current
        if (convId) {
          streamingMsgIdsRef.current.delete(convId)
        }
        setLoading(false)
        setRecalling(false)
      } else if (data.type === 'error') {
        // Surface error from backend
        console.error('WS Error from server:', data.detail)
        setLoading(false)
        setRecalling(false)
      } else if (data.type === 'conversation_created') {
        // New conversation was auto-created by backend
        const newId = data.conversation_id
        activeConvIdRef.current = newId
        // Safety path: backend sends conversation_created BEFORE streaming, so
        // this normally holds nothing — but if chunks raced ahead, surface them.
        if (pendingChunksRef.current) {
          const pending = pendingChunksRef.current
          pendingChunksRef.current = ''
          const assistantMessage: Message = {
            id: `streaming-${newId}-${Date.now()}`,
            role: 'assistant',
            content: pending,
            timestamp: new Date().toISOString()
          }
          addMessage(newId, assistantMessage)
          streamingMsgIdsRef.current.set(newId, assistantMessage.id)
        }
        setCurrentConversation(newId)
      } else if (data.type === 'message' && currentConversationId) {
        // Non-streaming fallback (legacy)
        const assistantMessage: Message = {
          id: data.id || Date.now().toString(),
          role: 'assistant',
          content: data.content,
          timestamp: new Date().toISOString()
        }
        addMessage(currentConversationId, assistantMessage)
        setLoading(false)
        setRecalling(false)
      } else if (data.type === 'stream_start') {
        setLoading(true)
      } else if (data.type === 'memory_recall') {
        setRecalling(true)
        if (data.context) {
          addMemoryContext(data.context)
        }
      } else if (data.type === 'connected') {
        console.log('WS authenticated as user:', data.user_id)
      } else if (data.type && data.type.startsWith('task_')) {
        useTaskStore.getState().handleWebSocketEvent(data)
      }
    }

    ws.current.onclose = () => {
      console.log('WS Disconnected, reconnecting...')
      reconnectTimeout.current = setTimeout(connect, 3000)
    }

    ws.current.onerror = (error) => {
      console.error('WS Error:', error)
    }
  }, [token, currentConversationId, addMessage, updateMessage, setLoading, setCurrentConversation, setRecalling, addMemoryContext])

  useEffect(() => {
    connect()
    return () => {
      ws.current?.close()
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current)
    }
  }, [connect])

  const sendMessage = (content: string) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      // Set loading immediately so the UI shows the streaming indicator
      setLoading(true)
      const payload: Record<string, string> = {
        type: 'message',
        content
      }
      // Only include conversation_id if one exists — backend auto-creates when omitted
      const convId = currentConversationId
      if (convId) {
        payload.conversation_id = convId
      }
      // Sync ref so the onmessage handler has the latest value
      activeConvIdRef.current = convId
      ws.current.send(JSON.stringify(payload))
    }
  }

  return { sendMessage }
}
