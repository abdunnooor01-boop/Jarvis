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
