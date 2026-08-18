import React, { useState, useRef, useEffect, useCallback } from 'react'
import { Loader2, Mic, MicOff, Volume2, VolumeX } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { useChatStore, Message } from '../stores/chat'
import { useAuthStore } from '../stores/auth'
import { useWebSocket } from '../hooks/useWebSocket'
import JarvisFace from './JarvisFace'

// ---------------------------------------------------------------------------
// Speech recognition helpers
// ---------------------------------------------------------------------------
const SpeechRecognitionAPI =
  (typeof window !== 'undefined' &&
    (window.SpeechRecognition || (window as any).webkitSpeechRecognition)) ||
  null

const isSpeechSupported = SpeechRecognitionAPI !== null

// ---------------------------------------------------------------------------
// Speech synthesis (text-to-speech)
// ---------------------------------------------------------------------------
const synth = typeof window !== 'undefined' ? window.speechSynthesis : null

/** Male first names that indicate a masculine voice when they appear in a voice's name. */
const MALE_VOICE_NAMES = [
  'david', 'mark', 'daniel', 'george', 'james', 'john', 'michael', 'guy', 'ryan',
  'alex', 'peter', 'thomas', 'christopher', 'eric', 'william', 'brian', 'paul',
  'samuel', 'robert', 'richard', 'charles', 'matthew', 'andrew', 'steven', 'aaron',
  'adam', 'benjamin', 'jacob', 'joseph', 'kevin', 'stephen', 'nick', 'tony', 'henry',
  'oliver', 'arthur', 'harry', 'edward', 'albert', 'jack', 'leo', 'oscar',
]

/** Find a male voice (British-first), falling back to any UK/en voice, then default. */
function getMaleVoice(): SpeechSynthesisVoice | null {
  if (!synth) return null
  const voices = synth.getVoices()
  const nameHasMale = (v: SpeechSynthesisVoice) => /male/i.test(v.name)
  const nameHasMaleFirstName = (v: SpeechSynthesisVoice) => {
    const n = v.name.toLowerCase()
    return MALE_VOICE_NAMES.some((name) => new RegExp(`\\b${name}\\b`).test(n))
  }
  // 1. en-GB voices whose name is explicitly male or contains a male first name
  const britishMale = voices.find(
    (v) => v.lang.toLowerCase().startsWith('en-gb') && (nameHasMale(v) || nameHasMaleFirstName(v))
  )
  if (britishMale) return britishMale
  // 2. ANY-language voice whose name contains "male" (e.g. "Google UK English Male")
  const anyMale = voices.find(nameHasMale)
  if (anyMale) return anyMale
  // 3. en-* voices whose name contains a male first name from the list
  const englishMale = voices.find((v) => v.lang.toLowerCase().startsWith('en') && nameHasMaleFirstName(v))
  if (englishMale) return englishMale
  // 4. fallbacks: any en-GB, any en-*, then the first available voice
  const british = voices.find((v) => v.lang.toLowerCase().startsWith('en-gb'))
  if (british) return british
  const english = voices.find((v) => v.lang.toLowerCase().startsWith('en'))
  if (english) return english
  return voices[0] || null
}

/** Build a TTS utterance for the given text (shared by full and incremental speech). */
function buildUtterance(text: string, onEnd?: () => void): SpeechSynthesisUtterance | null {
  if (!synth) return null
  const cleanText = text
    .replace(/```[\s\S]*?```/g, '')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/[*_~#>`|\[\]()]/g, '')
    .replace(/\n{2,}/g, '. ')
    .replace(/\n/g, ' ')
    .trim()
  if (!cleanText) return null
  const utterance = new SpeechSynthesisUtterance(cleanText)
  utterance.rate = 1.0
  // Slight lower pitch for a more masculine tone
  utterance.pitch = 0.95
  utterance.volume = 1.0
  const voice = getMaleVoice()
  if (voice) utterance.voice = voice
  if (onEnd) utterance.onend = onEnd
  return utterance
}

/** Speak text, cancelling any currently playing speech first. */
function speakText(text: string, onEnd?: () => void) {
  if (!synth) return
  synth.cancel()
  const utterance = buildUtterance(text, onEnd)
  if (utterance) synth.speak(utterance)
}

/** Queue text WITHOUT cancelling — for incremental sentence-level TTS. */
function speakSentence(text: string) {
  if (!synth) return
  const utterance = buildUtterance(text)
  if (utterance) synth.speak(utterance)
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
const ChatWindow: React.FC = () => {
  const { currentConversationId, messages, isLoading, historyLoading, addMessage, setLoading, loadHistory } = useChatStore()
  const { token } = useAuthStore()
  const scrollRef = useRef<HTMLDivElement>(null)
  const { sendMessage } = useWebSocket()
  // Load message history whenever the active conversation changes (initial
  // conversation after refresh, sidebar selection, or a WS-created one — the
  // store skips conversations that already have local/streaming messages).
  useEffect(() => {
    if (currentConversationId && token) {
      loadHistory(currentConversationId, token)
    }
    // loadHistory reads live state internally and is stable; only re-run on
    // conversation/token changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentConversationId, token])

  // Voice input state
  const [isListening, setIsListening] = useState(false)
  const [micError, setMicError] = useState<string | null>(null)
  const [textInput, setTextInput] = useState('')
  const recognitionRef = useRef<InstanceType<typeof SpeechRecognitionAPI> | null>(null)

  // Voice output (TTS) state
  const [voiceEnabled, setVoiceEnabled] = useState(true)
  const [speakingMsgId, setSpeakingMsgId] = useState<string | null>(null)

  // Track which messages have been fully spoken (message id → content)
  const spokenContentRef = useRef<Map<string, string>>(new Map())
  // Track char offset already spoken per message (for incremental sentence-level TTS)
  const spokenCharRef = useRef<Map<string, number>>(new Map())

  // Show messages from the current conversation, plus any pending messages
  // sent before a conversation was created (first message flow)
  const [pendingMessages, setPendingMessages] = useState<Message[]>([])
  const currentMessages = currentConversationId
    ? [...pendingMessages, ...(messages[currentConversationId] || [])]
    : pendingMessages

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [currentMessages, isLoading])

  // Auto-speak the FINAL reply once streaming completes (or full content for
  // non-streamed messages). Uses spokenCharRef to speak only the unsaid tail
  // if incremental sentence TTS already covered most of it.
  useEffect(() => {
    if (!voiceEnabled || !currentMessages.length || isLoading) return
    const lastMsg = currentMessages[currentMessages.length - 1]
    if (lastMsg.role !== 'assistant') return
    if (spokenContentRef.current.get(lastMsg.id) === lastMsg.content) return
    const offset = spokenCharRef.current.get(lastMsg.id) || 0
    const unsaid = lastMsg.content.slice(offset)
    spokenContentRef.current.set(lastMsg.id, lastMsg.content)
    spokenCharRef.current.set(lastMsg.id, lastMsg.content.length)
    if (unsaid.trim()) {
      const timer = setTimeout(() => {
        speakText(unsaid, () => setSpeakingMsgId(null))
        setSpeakingMsgId(lastMsg.id)
      }, 300)
      return () => clearTimeout(timer)
    }
  }, [currentMessages, isLoading, voiceEnabled])

  // Voice-first: speak completed sentences as they stream in, so the voice
  // starts within ~1–2s instead of waiting for the full reply.
  useEffect(() => {
    if (!voiceEnabled || !isLoading || !currentMessages.length) return
    const lastMsg = currentMessages[currentMessages.length - 1]
    if (lastMsg.role !== 'assistant') return
    const content = lastMsg.content
    const offset = spokenCharRef.current.get(lastMsg.id) || 0
    if (content.length <= offset) return
    const newText = content.slice(offset)
    // Extract complete sentences (ending with . ! ? followed by whitespace or end)
    const sentenceRe = /[^.!?]+[.!?]+(?=\s|$)/g
    const matches = newText.match(sentenceRe) || []
    let consumed = 0
    for (const sentence of matches) {
      const trimmed = sentence.trim()
      if (trimmed) speakSentence(trimmed)
      consumed += sentence.length
    }
    if (consumed > 0) {
      spokenCharRef.current.set(lastMsg.id, offset + consumed)
    }
  }, [currentMessages, isLoading, voiceEnabled])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try { recognitionRef.current.abort() } catch { /* ignore */ }
      }
      if (synth) synth.cancel()
    }
  }, [])

  // When a conversation is created (first message sent), move pending messages
  // into the real conversation so they appear in the chat history
  useEffect(() => {
    if (currentConversationId && pendingMessages.length > 0) {
      pendingMessages.forEach((msg) => addMessage(currentConversationId, msg))
      setPendingMessages([])
    }
  }, [currentConversationId, pendingMessages, addMessage])

  /** Send a transcribed message to the chat */
  const sendTranscribed = useCallback((text: string) => {
    if (!text.trim()) return
    if (synth) synth.cancel()
    setSpeakingMsgId(null)
    // Reset speech tracking so the next reply starts fresh
    spokenContentRef.current.clear()
    spokenCharRef.current.clear()
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      timestamp: new Date().toISOString()
    }
    // If no conversation exists yet, queue locally and let the backend
    // create one. The conversation_created event will set the ID.
    if (currentConversationId) {
      addMessage(currentConversationId, userMessage)
    } else {
      setPendingMessages((prev) => [...prev, userMessage])
    }
    sendMessage(text)
    setLoading(true)
  }, [currentConversationId, addMessage, sendMessage, setLoading])

  // -----------------------------------------------------------------------
  // Voice input handling
  // -----------------------------------------------------------------------
  const toggleListening = useCallback(() => {
    if (isListening) {
      if (recognitionRef.current) {
        try { recognitionRef.current.stop() } catch { /* ignore */ }
        recognitionRef.current = null
      }
      setIsListening(false)
      setMicError(null)
      return
    }

    if (!SpeechRecognitionAPI) {
      setMicError('Speech recognition not supported in this browser')
      return
    }

    try {
      const recognition = new SpeechRecognitionAPI()
      recognition.lang = 'en-US'
      recognition.interimResults = false
      recognition.continuous = false

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript
        if (transcript) {
          sendTranscribed(transcript)
        }
      }

      recognition.onerror = (event: any) => {
        console.error('Speech recognition error', event.error)
        if (event.error === 'not-allowed') {
          setMicError('Microphone permission denied')
        } else if (event.error === 'no-speech') {
          setMicError(null)
        } else {
          setMicError(`Mic error: ${event.error}`)
        }
        setIsListening(false)
        recognitionRef.current = null
      }

      recognition.onend = () => {
        setIsListening(false)
        recognitionRef.current = null
      }

      recognition.start()
      recognitionRef.current = recognition
      setIsListening(true)
      setMicError(null)
    } catch (err: any) {
      console.error('Failed to start speech recognition', err)
      setMicError(`Failed to start: ${err.message}`)
      setIsListening(false)
    }
  }, [isListening, sendTranscribed])

  // -----------------------------------------------------------------------
  // Voice output handling
  // -----------------------------------------------------------------------
  const handleReplay = (msgId: string, content: string) => {
    if (speakingMsgId === msgId) {
      if (synth) synth.cancel()
      setSpeakingMsgId(null)
      return
    }
    if (synth) synth.cancel()
    speakText(content, () => setSpeakingMsgId(null))
    setSpeakingMsgId(msgId)
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950">
      {/* Jarvis Face — always visible at the top */}
      <div className="flex-shrink-0 pt-2 pb-1 flex flex-col items-center">
        <JarvisFace
          isListening={isListening}
          isSpeaking={speakingMsgId !== null}
          isThinking={isLoading}
        />
      </div>

      {/* Conversation scroll area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 pb-2 space-y-4">
        {currentMessages.length === 0 && !isLoading && (
          <div className="flex flex-col items-center justify-center pt-4">
            {historyLoading ? (
              <p className="text-xs text-slate-500 italic flex items-center gap-2">
                <Loader2 size={12} className="animate-spin" /> Loading history...
              </p>
            ) : (
              <p className="text-xs text-slate-600 italic">Say something to start...</p>
            )}
          </div>
        )}

        {currentMessages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}
          >
            <div className={`max-w-[80%] flex flex-col gap-1 ${
              msg.role === 'assistant' ? 'items-start' : 'items-end'
            }`}>
              {/* Role label */}
              <span className={`text-[10px] uppercase tracking-widest font-semibold px-1 ${
                msg.role === 'assistant' ? 'text-indigo-500/60' : 'text-slate-500/60'
              }`}>
                {msg.role === 'assistant' ? 'Jarvis' : 'You'}
              </span>
              <div
                className={`rounded-2xl px-4 py-3 ${
                  msg.role === 'user'
                    ? 'bg-indigo-600/20 text-slate-200 rounded-br-md'
                    : 'bg-slate-800/60 text-slate-300 rounded-bl-md border border-slate-700/30'
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
              {/* Speaker icon for assistant messages */}
              {msg.role === 'assistant' && synth && (
                <button
                  onClick={() => handleReplay(msg.id, msg.content)}
                  title={speakingMsgId === msg.id ? 'Stop speaking' : 'Read aloud (British voice)'}
                  className={`flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-md transition-colors ${
                    speakingMsgId === msg.id
                      ? 'text-indigo-400 bg-indigo-900/30'
                      : 'text-slate-600 hover:text-indigo-400 hover:bg-slate-800/50'
                  }`}
                >
                  {speakingMsgId === msg.id ? (
                    <><VolumeX size={10} /><span>Stop</span></>
                  ) : (
                    <><Volume2 size={10} /><span>Listen again</span></>
                  )}
                </button>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-slate-800/40 rounded-2xl px-4 py-3 rounded-tl-md border border-slate-700/20">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
                <span className="text-xs text-slate-500 italic">Thinking...</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Voice-only control bar */}
      <div className="flex-shrink-0 px-6 py-4 bg-gradient-to-t from-slate-950 via-slate-950 to-transparent">
        <div className="max-w-xs mx-auto flex items-center justify-center gap-4">
          {/* Big Mic button — the primary action */}
          {isSpeechSupported && (
            <button
              onClick={toggleListening}
              title={isListening ? 'Stop listening' : 'Tap and speak'}
              className={`rounded-full transition-all duration-300 ${
                isListening
                  ? 'bg-red-500 text-white p-4 scale-110 shadow-lg shadow-red-500/40 mic-pulse'
                  : 'bg-indigo-600 hover:bg-indigo-500 text-white p-5 shadow-lg hover:shadow-xl hover:scale-105 shadow-indigo-600/20'
              }`}
            >
              {isListening ? <MicOff size={24} /> : <Mic size={26} />}
            </button>
          )}
        </div>
        {/* Text input fallback - always visible */}
        <div className="max-w-lg mx-auto mt-3 flex items-center gap-2">
          <input
            type="text"
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && textInput.trim()) {
                sendTranscribed(textInput.trim())
                setTextInput('')
              }
            }}
            placeholder={isSpeechSupported ? "Type a message..." : "Enter your message..."}
            className="flex-1 bg-slate-800/60 border border-slate-700/50 rounded-xl px-4 py-2.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 transition-all"
          />
          <button
            onClick={() => {
              if (textInput.trim()) {
                sendTranscribed(textInput.trim())
                setTextInput('')
              }
            }}
            disabled={!textInput.trim()}
            className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl px-4 py-2.5 text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </div>

        {/* Status messages */}
        <div className="flex items-center justify-center mt-3 gap-3">
          {isListening && (
            <span className="flex items-center gap-1.5 text-xs text-red-400 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
              Listening...
            </span>
          )}
          {micError && (
            <span className="text-xs text-amber-400/80">{micError}</span>
          )}
          {!isListening && !micError && isSpeechSupported && voiceEnabled && (
            <span className="text-[10px] text-slate-600">Tap the mic to speak</span>
          )}
          {!isListening && !micError && isSpeechSupported && !voiceEnabled && (
            <span className="text-[10px] text-slate-600">Voice output off</span>
          )}
          {synth && (
            <button
              onClick={() => {
                setVoiceEnabled((v) => !v)
                if (voiceEnabled && synth) { synth.cancel(); setSpeakingMsgId(null); spokenContentRef.current.clear(); spokenCharRef.current.clear() }
              }}
              title={voiceEnabled ? 'Voice output on' : 'Voice output off'}
              className={`text-[10px] px-2 py-1 rounded transition-colors ${
                voiceEnabled
                  ? 'text-indigo-400/60 hover:text-indigo-400'
                  : 'text-slate-600 hover:text-slate-400'
              }`}
            >
              {voiceEnabled ? 'Voice: ON' : 'Voice: OFF'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default ChatWindow