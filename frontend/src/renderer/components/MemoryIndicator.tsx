import React, { useEffect, useState } from 'react'
import { Brain, Sparkles } from 'lucide-react'
import { useMemoryStore } from '../stores/memory'

export const MemoryIndicator: React.FC = () => {
  const { isRecalling, recentContext, clearRecentContext } = useMemoryStore()
  const [showToast, setShowToast] = useState(false)
  const [toastCount, setToastCount] = useState(0)

  useEffect(() => {
    if (recentContext) {
      let count = 0
      try {
        const parsed = JSON.parse(recentContext)
        if (Array.isArray(parsed)) {
          count = parsed.length
        } else if (parsed && typeof parsed === 'object') {
          count = Object.keys(parsed).length
        }
      } catch {
        // Fallback for list format
        const lines = recentContext.split('\n').map(l => l.trim()).filter(l => l.length > 0)
        const listItems = lines.filter(l => l.startsWith('-') || l.startsWith('*') || /^\d+\./.test(l))
        count = listItems.length > 0 ? listItems.length : lines.length
      }

      setToastCount(count)
      setShowToast(true)

      const timer = setTimeout(() => {
        setShowToast(false)
        clearRecentContext()
      }, 3000)

      return () => clearTimeout(timer)
    }
  }, [recentContext, clearRecentContext])

  return (
    <div className="w-full flex flex-col items-center justify-center pointer-events-none relative z-50">
      {/* Toast Alert */}
      {showToast && toastCount > 0 && (
        <div className="fixed bottom-24 left-1/2 transform -translate-x-1/2 bg-indigo-600 dark:bg-indigo-900 text-white px-4 py-2 rounded-xl shadow-lg flex items-center gap-2 border border-indigo-500/30 transition-all duration-300 ease-out animate-bounce pointer-events-auto">
          <Sparkles className="w-4 h-4 text-indigo-200 animate-pulse" />
          <span className="text-sm font-medium">Recalled {toastCount} memories</span>
        </div>
      )}

      {/* Recalling Indicator */}
      {isRecalling && (
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-50/80 dark:bg-indigo-950/40 border border-indigo-100 dark:border-indigo-900/40 text-indigo-600 dark:text-indigo-400 animate-pulse my-2">
          <Brain className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400 animate-spin" style={{ animationDuration: '3s' }} />
          <span className="text-xs font-semibold tracking-wide">Jarvis is recalling...</span>
        </div>
      )}
    </div>
  )
}

export default MemoryIndicator
