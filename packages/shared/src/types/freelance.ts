export interface TaskTemplate {
  id: string
  name: string
  description: string
  price: number
  estimated_time: string
}

export interface FreelanceJob {
  id: string
  template_id: string | null
  task_type: string
  customer_email: string
  details: string
  amount_paid: number
  status: 'paid' | 'processing' | 'completed' | 'delivered'
  created_at: string
  payment_url?: string
  summary?: string
  deliverables?: string[]
}
