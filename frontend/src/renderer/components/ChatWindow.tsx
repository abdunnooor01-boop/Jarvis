import React, { useState, useRef, useEffect } from 'react'
import { Send, Loader2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { useChatStore, Message } from '../stores/chat'
import { useWebSocket } from '../hooks/useWebSocket'

const ChatWindow: React.FC = () => {
  const { currentConversationId, messages, isLoading, addMessage, setLoading } = useChatStore()
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const { sendMessage } = useWebSocket()

  const currentMessages = currentConversationId ? messages[currentConversationId] || [] : []

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [currentMessages, isLoading])

  const handleSend = () => {
    if (!input.trim() || !currentConversationId) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date().toISOString()
    }

    addMessage(currentConversationId, userMessage)
    sendMessage(input)
    setInput('')
    setLoading(true)
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-6">
        {currentMessages.length === 0 && !isLoading && (
          <div className="h-full flex flex-col items-center justify-center text-slate-400 space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-slate-50 dark:bg-slate-800 flex items-center justify-center">
              <Send size={24} className="rotate-[-45deg]" />
            </div>
            <p className="text-sm font-medium">How can I help you today?</p>
          </div>
        )}

        {currentMessages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`chat-bubble ${
                msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'
              }`}
            >
              {msg.role === 'user' ? (
                msg.content
              ) : (
                <ReactMarkdown className="prose dark:prose-invert prose-sm max-w-none">
                  {msg.content}
                </ReactMarkdown>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="chat-bubble chat-bubble-assistant flex items-center gap-2">
              <Loader2 size={16} className="animate-spin text-indigo-500" />
              <span className="text-slate-500 italic">Jarvis is thinking...</span>
            </div>
          </div>
        )}
      </div>

      <div className="p-4 border-t border-slate-200 dark:border-slate-800">
        <div className="max-w-3xl mx-auto flex gap-2">
          <textarea
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            placeholder="Type a message..."
            className="flex-1 bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || !currentConversationId}
            className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:hover:bg-indigo-600 text-white rounded-xl p-3 transition-colors"
          >
            <Send size={20} />
          </button>
        </div>
        <p className="text-[10px] text-center text-slate-400 mt-2">
          Jarvis can make mistakes. Check important info.
        </p>
      </div>
    </div>
  )
}

export default ChatWindow
