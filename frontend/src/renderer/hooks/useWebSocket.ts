import { useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '../stores/auth'
import { useChatStore, Message } from '../stores/chat'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/v1/chat'

export const useWebSocket = () => {
  const { token } = useAuthStore()
  const { currentConversationId, addMessage, setLoading } = useChatStore()
  const ws = useRef<WebSocket | null>(null)
  const reconnectTimeout = useRef<NodeJS.Timeout>()

  const connect = useCallback(() => {
    if (!token) return

    ws.current = new WebSocket(WS_URL)

    ws.current.onopen = () => {
      console.log('WS Connected')
      // Send auth token
      ws.current?.send(JSON.stringify({ type: 'auth', token }))
    }

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data)
      
      if (data.type === 'message' && currentConversationId) {
        const assistantMessage: Message = {
          id: data.id || Date.now().toString(),
          role: 'assistant',
          content: data.content,
          timestamp: new Date().toISOString()
        }
        addMessage(currentConversationId, assistantMessage)
        setLoading(false)
      } else if (data.type === 'stream_start') {
        setLoading(true)
      }
    }

    ws.current.onclose = () => {
      console.log('WS Disconnected, reconnecting...')
      reconnectTimeout.current = setTimeout(connect, 3000)
    }

    ws.current.onerror = (error) => {
      console.error('WS Error:', error)
    }
  }, [token, currentConversationId, addMessage, setLoading])

  useEffect(() => {
    connect()
    return () => {
      ws.current?.close()
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current)
    }
  }, [connect])

  const sendMessage = (content: string) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({
        type: 'message',
        conversation_id: currentConversationId,
        content
      }))
    }
  }

  return { sendMessage }
}
