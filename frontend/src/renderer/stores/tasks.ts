import { create } from 'zustand'
import { useAuthStore } from './auth'

export interface TaskStep {
  id: string
  plan_id: string
  step_number: number
  tool_name: string
  tool_params: Record<string, any>
  description: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped' | 'cancelled'
  result?: any
  error?: string
  retry_count: number
  started_at?: string
  completed_at?: string
}

export interface TaskPlan {
  id: string
  user_id: string
  goal: string
  status: 'pending' | 'approved' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'
  error_mode: 'abort' | 'skip' | 'retry'
  max_retries: number
  total_steps: number
  completed_steps: number
  failed_steps: number
  steps: TaskStep[]
  created_at: string
  updated_at: string
  started_at?: string
  completed_at?: string
}

interface TaskState {
  plans: TaskPlan[]
  activePlan: TaskPlan | null
  isPlanning: boolean
  isExecuting: boolean
  isLoading: boolean
  error: string | null
  fetchPlans: () => Promise<void>
  createPlan: (goal: string) => Promise<TaskPlan | null>
  executePlan: (id: string) => Promise<void>
  pausePlan: (id: string) => Promise<void>
  resumePlan: (id: string) => Promise<void>
  cancelPlan: (id: string) => Promise<void>
  setActivePlan: (plan: TaskPlan | null) => void
  handleWebSocketEvent: (event: any) => void
}

import { getApiUrl } from '../utils/env'

const API_URL = getApiUrl()

export const useTaskStore = create<TaskState>((set, get) => ({
  plans: [],
  activePlan: null,
  isPlanning: false,
  isExecuting: false,
  isLoading: false,
  error: null,

  setActivePlan: (plan) => {
    set({ activePlan: plan })
  },

  fetchPlans: async () => {
    set({ isLoading: true, error: null })
    try {
      const token = useAuthStore.getState().token
      const response = await fetch(`${API_URL}/api/v1/tasks`, {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch task plans')
      }

      const data = await response.json()
      set({ plans: data.items || [], isLoading: false })
    } catch (err: any) {
      set({ error: err.message || 'An error occurred', isLoading: false })
    }
  },

  createPlan: async (goal: string) => {
    set({ isPlanning: true, error: null })
    try {
      const token = useAuthStore.getState().token
      const response = await fetch(`${API_URL}/api/v1/tasks/plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ goal })
      })

      if (!response.ok) {
        throw new Error('Failed to create plan')
      }

      const plan: TaskPlan = await response.json()
      set((state) => ({
        plans: [plan, ...state.plans],
        activePlan: plan,
        isPlanning: false
      }))
      return plan
    } catch (err: any) {
      set({ error: err.message || 'An error occurred', isPlanning: false })
      return null
    }
  },

  executePlan: async (id: string) => {
    set({ error: null })
    try {
      const token = useAuthStore.getState().token
      const response = await fetch(`${API_URL}/api/v1/tasks/${id}/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('Failed to start plan execution')
      }

      set((state) => {
        const updatedPlans = state.plans.map((p) =>
          p.id === id ? { ...p, status: 'running' as const, started_at: new Date().toISOString() } : p
        )
        const updatedActive = state.activePlan?.id === id
          ? { ...state.activePlan, status: 'running' as const, started_at: new Date().toISOString() }
          : state.activePlan
        return {
          plans: updatedPlans,
          activePlan: updatedActive,
          isExecuting: true
        }
      })
    } catch (err: any) {
      set({ error: err.message || 'An error occurred' })
    }
  },

  pausePlan: async (id: string) => {
    try {
      const token = useAuthStore.getState().token
      const response = await fetch(`${API_URL}/api/v1/tasks/${id}/pause`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('Failed to pause plan')
      }

      set((state) => {
        const updatedPlans = state.plans.map((p) =>
          p.id === id ? { ...p, status: 'paused' as const } : p
        )
        const updatedActive = state.activePlan?.id === id
          ? { ...state.activePlan, status: 'paused' as const }
          : state.activePlan
        return {
          plans: updatedPlans,
          activePlan: updatedActive
        }
      })
    } catch (err: any) {
      set({ error: err.message || 'An error occurred' })
    }
  },

  resumePlan: async (id: string) => {
    try {
      const token = useAuthStore.getState().token
      const response = await fetch(`${API_URL}/api/v1/tasks/${id}/resume`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('Failed to resume plan')
      }

      set((state) => {
        const updatedPlans = state.plans.map((p) =>
          p.id === id ? { ...p, status: 'running' as const } : p
        )
        const updatedActive = state.activePlan?.id === id
          ? { ...state.activePlan, status: 'running' as const }
          : state.activePlan
        return {
          plans: updatedPlans,
          activePlan: updatedActive
        }
      })
    } catch (err: any) {
      set({ error: err.message || 'An error occurred' })
    }
  },

  cancelPlan: async (id: string) => {
    try {
      const token = useAuthStore.getState().token
      const response = await fetch(`${API_URL}/api/v1/tasks/${id}/cancel`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('Failed to cancel plan')
      }

      set((state) => {
        const updatedPlans = state.plans.map((p) =>
          p.id === id
            ? {
                ...p,
                status: 'cancelled' as const,
                completed_at: new Date().toISOString(),
                steps: p.steps.map((s) => (s.status === 'pending' ? { ...s, status: 'cancelled' as const } : s))
              }
            : p
        )
        const updatedActive = state.activePlan?.id === id
          ? {
              ...state.activePlan,
              status: 'cancelled' as const,
              completed_at: new Date().toISOString(),
              steps: state.activePlan.steps.map((s) =>
                s.status === 'pending' ? { ...s, status: 'cancelled' as const } : s
              )
            }
          : state.activePlan
        return {
          plans: updatedPlans,
          activePlan: updatedActive,
          isExecuting: false
        }
      })
    } catch (err: any) {
      set({ error: err.message || 'An error occurred' })
    }
  },

  handleWebSocketEvent: (event: any) => {
    const { type, plan_id, step_id, step_order, result, error, attempt } = event
    if (!plan_id) return

    set((state) => {
      // Find the plan we are updating
      const planIndex = state.plans.findIndex((p) => p.id === plan_id)
      if (planIndex === -1 && !state.activePlan) return {}

      const plansCopy = [...state.plans]
      let plan = planIndex !== -1 ? { ...plansCopy[planIndex] } : null
      let activePlan = state.activePlan?.id === plan_id ? { ...state.activePlan } : null

      const updatePlanAndActive = (updater: (p: TaskPlan) => TaskPlan) => {
        if (plan) {
          plan = updater(plan)
          plansCopy[planIndex] = plan
        }
        if (activePlan) {
          activePlan = updater(activePlan)
        }
      }

      switch (type) {
        case 'task_started':
          updatePlanAndActive((p) => ({
            ...p,
            status: 'running',
            started_at: new Date().toISOString()
          }))
          return { plans: plansCopy, activePlan, isExecuting: true }

        case 'task_completed':
          updatePlanAndActive((p) => ({
            ...p,
            status: 'completed',
            completed_at: new Date().toISOString()
          }))
          return { plans: plansCopy, activePlan, isExecuting: false }

        case 'task_failed':
          updatePlanAndActive((p) => ({
            ...p,
            status: 'failed',
            completed_at: new Date().toISOString()
          }))
          return { plans: plansCopy, activePlan, isExecuting: false }

        case 'task_paused':
          updatePlanAndActive((p) => ({
            ...p,
            status: 'paused'
          }))
          return { plans: plansCopy, activePlan }

        case 'task_resumed':
          updatePlanAndActive((p) => ({
            ...p,
            status: 'running'
          }))
          return { plans: plansCopy, activePlan }

        case 'task_cancelled':
          updatePlanAndActive((p) => ({
            ...p,
            status: 'cancelled',
            completed_at: new Date().toISOString(),
            steps: p.steps.map((s) => (s.status === 'pending' ? { ...s, status: 'cancelled' } : s))
          }))
          return { plans: plansCopy, activePlan, isExecuting: false }

        case 'task_step_start':
          updatePlanAndActive((p) => {
            const steps = p.steps.map((s) => {
              if (s.id === step_id || s.step_number === step_order) {
                return { ...s, status: 'running' as const, started_at: new Date().toISOString() }
              }
              return s
            })
            return { ...p, steps }
          })
          return { plans: plansCopy, activePlan }

        case 'task_step_complete':
          updatePlanAndActive((p) => {
            let incrementCompleted = false
            const steps = p.steps.map((s) => {
              if (s.id === step_id || s.step_number === step_order) {
                if (s.status !== 'completed') incrementCompleted = true
                return {
                  ...s,
                  status: 'completed' as const,
                  result,
                  completed_at: new Date().toISOString()
                }
              }
              return s
            })
            return {
              ...p,
              steps,
              completed_steps: incrementCompleted ? p.completed_steps + 1 : p.completed_steps
            }
          })
          return { plans: plansCopy, activePlan }

        case 'task_step_retry':
          updatePlanAndActive((p) => {
            const steps = p.steps.map((s) => {
              if (s.id === step_id || s.step_number === step_order) {
                return { ...s, retry_count: attempt, error }
              }
              return s
            })
            return { ...p, steps }
          })
          return { plans: plansCopy, activePlan }

        case 'task_step_skipped':
          updatePlanAndActive((p) => {
            let incrementFailed = false
            const steps = p.steps.map((s) => {
              if (s.id === step_id || s.step_number === step_order) {
                if (s.status !== 'skipped') incrementFailed = true
                return {
                  ...s,
                  status: 'skipped' as const,
                  error,
                  completed_at: new Date().toISOString()
                }
              }
              return s
            })
            return {
              ...p,
              steps,
              failed_steps: incrementFailed ? p.failed_steps + 1 : p.failed_steps
            }
          })
          return { plans: plansCopy, activePlan }

        case 'task_step_failed':
          updatePlanAndActive((p) => {
            let incrementFailed = false
            const steps = p.steps.map((s) => {
              if (s.id === step_id || s.step_number === step_order) {
                if (s.status !== 'failed') incrementFailed = true
                return {
                  ...s,
                  status: 'failed' as const,
                  error,
                  completed_at: new Date().toISOString()
                }
              }
              return s
            })
            return {
              ...p,
              steps,
              failed_steps: incrementFailed ? p.failed_steps + 1 : p.failed_steps
            }
          })
          return { plans: plansCopy, activePlan }

        default:
          return {}
      }
    })
  }
}))
