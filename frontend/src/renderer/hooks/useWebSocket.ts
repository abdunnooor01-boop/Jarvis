import { useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '../stores/auth'
import { useChatStore, Message, ToolActionInfo } from '../stores/chat'
import { useMemoryStore } from '../stores/memory'
import { useTaskStore } from '../stores/tasks'

export interface ToolDecisionPayload {
  proposalId: string
  decision: 'approve' | 'deny'
  remember?: boolean
}

export type SendToolDecision = (payload: ToolDecisionPayload) => void

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
  const { setCurrentConversation, addMessage, updateMessage, setLoading } = useChatStore()
  const { setRecalling, addMemoryContext } = useMemoryStore()
  const ws = useRef<WebSocket | null>(null)
  const reconnectTimeout = useRef<NodeJS.Timeout>()
  const pingInterval = useRef<NodeJS.Timeout>()
  // True when WE intentionally closed the socket (cleanup/logout) — a close
  // from the effect cleanup must not trigger the reconnect loop.
  const manuallyClosedRef = useRef(false)
  // Content sent while the socket was down (reconnecting) — delivered on open
  const pendingMessageRef = useRef<string | null>(null)
  // Map conversationId → id of the in-progress assistant message being streamed
  const streamingMsgIdsRef = useRef<Map<string, string>>(new Map())
  // Ref to track the active conversation ID independently of the store (avoids
  // closure staleness when streaming begins before conversation_created sets it)
  const activeConvIdRef = useRef<string | null>(null)
  // Accumulate chunks that arrive before we know the conversation_id
  const pendingChunksRef = useRef<string>('')

  const connect = useCallback(() => {
    if (!token) return

    // Sync ref from store on every connect (read live state — the callback is
    // intentionally NOT recreated when the conversation changes, so the WS
    // socket survives conversation_created and mid-stream state updates).
    activeConvIdRef.current = useChatStore.getState().currentConversationId

    // Any future close of THIS socket is treated as an unexpected drop
    // (reconnect), unless it is the current socket being torn down on purpose.
    manuallyClosedRef.current = false
    const socket = new WebSocket(WS_URL)
    ws.current = socket

    // Keepalive: the public edge terminates idle WebSocket connections after a
    // few seconds, silently dropping any message sent on a stale-but-open
    // socket ("Thinking..." forever). Ping every 2s so the connection never
    // goes idle. The backend answers {"type":"ping"} with {"type":"pong"}.
    if (pingInterval.current) clearInterval(pingInterval.current)
    pingInterval.current = setInterval(() => {
      if (ws.current && ws.current.readyState === WebSocket.OPEN) {
        ws.current.send(JSON.stringify({ type: 'ping' }))
      }
    }, 2000)

    socket.onopen = () => {
      console.log('WS Connected')
      // Send auth token
      socket.send(JSON.stringify({ type: 'auth', token }))
      // Deliver any message that was queued while the socket was down
      if (pendingMessageRef.current) {
        const payload: Record<string, string> = {
          type: 'message',
          content: pendingMessageRef.current,
        }
        if (activeConvIdRef.current) payload.conversation_id = activeConvIdRef.current
        socket.send(JSON.stringify(payload))
        pendingMessageRef.current = null
      }
    }

    socket.onmessage = (event) => {
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
      } else if (data.type === 'message' && activeConvIdRef.current) {
        // Non-streaming fallback (legacy)
        const assistantMessage: Message = {
          id: data.id || Date.now().toString(),
          role: 'assistant',
          content: data.content,
          timestamp: new Date().toISOString()
        }
        addMessage(activeConvIdRef.current, assistantMessage)
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
      } else if (data.type === 'tool_call') {
        // Optimistic action-log entry — a proposal (or auto-approved result)
        // follows; both resolve it by tool_call_id.
        const convId = activeConvIdRef.current
        if (convId) {
          const action: ToolActionInfo = {
            toolCallId: data.tool_call_id,
            toolName: data.tool_name,
            arguments: data.arguments ?? {},
            status: 'requested',
            timestamp: new Date().toISOString(),
          }
          useChatStore.getState().addAction(convId, action)
        }
      } else if (data.type === 'tool_proposal') {
        // Approval needed — remember the proposal id so the owner's decision
        // can be sent back, and surface the pending card.
        const convId = activeConvIdRef.current
        if (convId) {
          useChatStore.getState().updateAction(convId, data.tool_call_id, {
            proposalId: data.proposal_id,
            reason: data.reason,
            status: 'pending',
          })
        }
      } else if (data.type === 'tool_result') {
        // Authoritative outcome from the backend (approved/denied/unavailable).
        const convId = activeConvIdRef.current
        if (convId) {
          const status = data.unavailable
            ? 'unavailable'
            : data.denied
              ? 'denied'
              : 'executed'
          useChatStore.getState().updateAction(convId, data.tool_call_id, {
            status,
            result: data.result ?? undefined,
            approval: data.approval,
          })
        }
      } else if (data.type && data.type.startsWith('task_')) {
        useTaskStore.getState().handleWebSocketEvent(data)
      }
    }

    socket.onclose = () => {
      console.log('WS Disconnected, reconnecting...')
      if (pingInterval.current) clearInterval(pingInterval.current)
      // Only reconnect when THIS socket is still the current one AND the close
      // wasn't an intentional teardown — stale sockets from effect churn must
      // not schedule extra connections.
      if (!manuallyClosedRef.current && ws.current === socket) {
        reconnectTimeout.current = setTimeout(connect, 3000)
      }
    }

    socket.onerror = (error) => {
      console.error('WS Error:', error)
    }
  }, [token, addMessage, updateMessage, setLoading, setCurrentConversation, setRecalling, addMemoryContext])

  useEffect(() => {
    connect()
    return () => {
      // Intentional teardown — mark so onclose does not schedule a reconnect.
      manuallyClosedRef.current = true
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current)
      if (pingInterval.current) clearInterval(pingInterval.current)
      ws.current?.close()
    }
  }, [connect])

  const sendMessage = (content: string) => {
    // Read the live conversation id so sends are never stale after a switch.
    const convId = useChatStore.getState().currentConversationId
    if (ws.current?.readyState === WebSocket.OPEN) {
      // Set loading immediately so the UI shows the streaming indicator
      setLoading(true)
      const payload: Record<string, string> = {
        type: 'message',
        content
      }
      // Only include conversation_id if one exists — backend auto-creates when omitted
      if (convId) {
        payload.conversation_id = convId
      }
      // Sync ref so the onmessage handler has the latest value
      activeConvIdRef.current = convId
      ws.current.send(JSON.stringify(payload))
    } else if (ws.current?.readyState === WebSocket.CONNECTING) {
      // Socket mid-handshake — queue and deliver on open so the message
      // is never silently dropped.
      pendingMessageRef.current = content
      activeConvIdRef.current = convId
      setLoading(true)
    } else {
      // Socket closed (reconnecting) — store the message; it is delivered
      // on the next successful connect (see onopen).
      pendingMessageRef.current = content
      activeConvIdRef.current = convId
      setLoading(true)
      connect()
    }
  }

  /** Send an owner approval decision for a tool proposal (Phase 15c). */
  const sendToolDecision = useCallback((payload: ToolDecisionPayload) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: 'tool_decision', ...payload }))
    }
  }, [])

  return { sendMessage, sendToolDecision }
}
