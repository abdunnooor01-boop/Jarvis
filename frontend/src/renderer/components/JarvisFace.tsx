import React from 'react'

/**
 * JarvisFace — animated assistant orb shown at the top of the chat.
 * Restored as a web (React DOM) port of the component that was lost when the
 * sandbox machine was replaced. Uses the same visual language as the mobile
 * RN version (glowing orb + pulse rings + status text) with pure CSS animations.
 */
interface JarvisFaceProps {
  isListening?: boolean
  isSpeaking?: boolean
  isThinking?: boolean
}

const JarvisFace: React.FC<JarvisFaceProps> = ({
  isListening = false,
  isSpeaking = false,
  isThinking = false,
}) => {
  const isActive = isListening || isSpeaking || isThinking
  const activeColor = isListening
    ? '#f87171' // red-400
    : isSpeaking
      ? '#818cf8' // indigo-400
      : isThinking
        ? '#f59e0b' // amber-500
        : '#3b82f6' // blue-500
  const glowColor = isListening
    ? 'rgba(248,113,113,0.55)'
    : isSpeaking
      ? 'rgba(129,140,248,0.55)'
      : isThinking
        ? 'rgba(245,158,11,0.5)'
        : 'rgba(59,130,246,0.45)'

  const waveBars = Array.from({ length: 7 })

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 8 }}>
      <div
        style={{
          position: 'relative',
          width: 128,
          height: 128,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {/* outer glow */}
        <div
          style={{
            position: 'absolute',
            width: 128,
            height: 128,
            borderRadius: 64,
            background: glowColor,
            filter: 'blur(14px)',
            transition: 'background 0.5s ease',
          }}
        />
        {/* pulse rings */}
        {isActive && (
          <>
            <div className="jarvis-pulse-ring" style={{ position: 'absolute', width: 128, height: 128, borderRadius: 64, border: '2px solid ' + activeColor }} />
            <div
              className="jarvis-pulse-ring jarvis-pulse-ring--slow"
              style={{ position: 'absolute', width: 100, height: 100, borderRadius: 50, border: '1px solid ' + activeColor }}
            />
          </>
        )}
        {/* core orb */}
        <div
          style={{
            position: 'absolute',
            width: 84,
            height: 84,
            borderRadius: 42,
            background: `radial-gradient(circle at 35% 30%, rgba(255,255,255,0.85), ${activeColor} 55%, rgba(2,6,23,0.9) 130%)`,
            boxShadow: `0 0 22px ${glowColor}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background 0.5s ease, box-shadow 0.5s ease',
          }}
        >
          <div style={{ width: 12, height: 12, borderRadius: 6, background: isListening || isSpeaking ? '#fff' : 'rgba(15,23,42,0.85)', transition: 'background 0.3s ease' }} />
        </div>
        {/* waveform */}
        {(isListening || isSpeaking) && (
          <div style={{ position: 'absolute', bottom: 2, left: 0, right: 0, display: 'flex', alignItems: 'flex-end', justifyContent: 'center', gap: 2, height: 20 }}>
            {waveBars.map((_, i) => (
              <div
                key={i}
                className="jarvis-wave-bar"
                style={{
                  width: 3,
                  height: 12,
                  borderRadius: 2,
                  background: activeColor,
                  animationDelay: `${i * 0.12}s`,
                }}
              />
            ))}
          </div>
        )}
      </div>
      {/* status text */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4, minHeight: 18 }}>
        {isListening && <span style={{ fontSize: 13, fontWeight: 500, color: '#f87171' }}>Listening...</span>}
        {isSpeaking && <span style={{ fontSize: 13, fontWeight: 500, color: '#818cf8' }}>Speaking...</span>}
        {isThinking && <span style={{ fontSize: 13, fontWeight: 500, color: '#f59e0b' }}>Thinking...</span>}
        {!isActive && <span style={{ fontSize: 14, fontWeight: 500, color: '#cbd5e1' }}>Jarvis</span>}
      </div>
      <style>{`
        @keyframes jarvis-pulse {
          0% { transform: scale(0.85); opacity: 0.8; }
          100% { transform: scale(1.25); opacity: 0; }
        }
        .jarvis-pulse-ring { animation: jarvis-pulse 1.8s ease-out infinite; }
        .jarvis-pulse-ring--slow { animation-duration: 2.4s; animation-delay: 0.3s; }
        @keyframes jarvis-wave {
          0%, 100% { transform: scaleY(0.4); }
          50% { transform: scaleY(1.6); }
        }
        .jarvis-wave-bar { animation: jarvis-wave 0.9s ease-in-out infinite; transform-origin: bottom; }
      `}</style>
    </div>
  )
}

export default JarvisFace