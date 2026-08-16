import React, { useState } from 'react'
import { useAuthStore } from '../stores/auth'
import { register, ApiError } from '../utils/api'

interface SignupProps {
  onSwitch: () => void
}

const Signup: React.FC<SignupProps> = ({ onSwitch }) => {
  const { setAuth } = useAuthStore()
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      const data = await register(email, password, displayName)
      await setAuth(data.access_token, { email, displayName })
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('Unable to reach the server. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="w-full max-w-sm p-8 bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800">
      <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-6">Create Account</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Display Name</label>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            required
            maxLength={100}
            autoComplete="name"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            required
            autoComplete="email"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            required
            minLength={8}
            autoComplete="new-password"
          />
          <p className="mt-1 text-[10px] text-slate-500">At least 8 characters, with uppercase, lowercase and a digit.</p>
        </div>
        {error && (
          <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{error}</p>
        )}
        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg py-2.5 text-sm font-semibold transition-colors"
        >
          {isSubmitting ? 'Creating account...' : 'Sign Up'}
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-500">
        Already have an account?{' '}
        <button onClick={onSwitch} className="text-indigo-600 hover:underline">
          Login
        </button>
      </p>
    </div>
  )
}

export default Signup
