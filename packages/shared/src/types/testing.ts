export interface TestPlan {
  id: string
  url: string
  criteria: string
  schedule: 'daily' | 'hourly' | 'on-demand'
  status: 'active' | 'inactive'
  last_run_at?: string | null
  pass_rate?: number | null
  created_at: string
}

export interface TestStepResult {
  id: string
  name: string
  status: 'passed' | 'failed' | 'pending'
  error?: string | null
  duration?: number
}

export interface TestRun {
  id: string
  plan_id: string
  plan_url?: string
  status: 'passed' | 'failed' | 'running' | 'queued'
  passed_count: number
  failed_count: number
  duration: number // in seconds
  created_at: string
  screenshots?: string[]
  results?: TestStepResult[]
}

export interface TestingSubscription {
  tier: 'Basic' | 'Pro'
  runs_used: number
  runs_limit: number
  is_active: boolean
  stripe_payment_link?: string | null
}
