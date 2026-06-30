import React, { useState } from 'react'
import { useAuthStore } from '../stores/auth'

interface LoginProps {
  onSwitch: () => void
}

const Login: React.FC<LoginProps> = ({ onSwitch }) => {
  const { setAuth } = useAuthStore()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // Mock login
    setAuth('mock-token', { email, displayName: email.split('@')[0] })
  }

  return (
    <div className="w-full max-w-sm p-8 bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800">
      <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-6">Welcome Back</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            required
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
          />
        </div>
        <button
          type="submit"
          className="w-full bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg py-2.5 text-sm font-semibold transition-colors"
        >
          Login
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-500">
        Don't have an account?{' '}
        <button onClick={onSwitch} className="text-indigo-600 hover:underline">
          Sign up
        </button>
      </p>
    </div>
  )
}

export default Login
