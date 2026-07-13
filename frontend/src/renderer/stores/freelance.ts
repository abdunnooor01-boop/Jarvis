import { create } from 'zustand'
import { useAuthStore } from './auth'

export interface TaskTemplate {
  id: string
  name: string
  description: string
  price: number
  estimated_time: string
}

export interface FreelanceJob {
  id: string
  template_id: string
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

interface FreelanceState {
  templates: TaskTemplate[]
  jobs: FreelanceJob[]
  activeJob: FreelanceJob | null
  isProcessing: boolean
  isLoading: boolean
  error: string | null
  earnings: {
    total_earned: number
    completed_jobs: number
  }

  fetchTemplates: () => Promise<void>
  createOrder: (
    templateId: string | null,
    details: { customer_email: string; specific_instructions: string; customer_name?: string; files?: string[] }
  ) => Promise<FreelanceJob | null>
  fetchJobs: () => Promise<void>
  fetchJob: (id: string) => Promise<void>
}

import { getApiUrl } from '../utils/env'

const API_URL = getApiUrl()

// Default mock templates
const MOCK_TEMPLATES: TaskTemplate[] = [
  {
    id: 'template-qa',
    name: 'QA Testing Run',
    description: 'Provide detailed automation test script runs for your web application with full screenshot reports and console logs analysis.',
    price: 49.99,
    estimated_time: '2 hours'
  },
  {
    id: 'template-copywriting',
    name: 'Technical Copywriting',
    description: 'Write a high-converting, search-engine-optimized technical blog post or developer-focused product documentation.',
    price: 29.99,
    estimated_time: '1 hour'
  },
  {
    id: 'template-scraping',
    name: 'Web Data Scraping',
    description: 'Scrape and clean structured tabular data from any public website, directory, or API according to your detailed specifications.',
    price: 39.99,
    estimated_time: '1.5 hours'
  },
  {
    id: 'template-support',
    name: 'Customer Support Automation',
    description: 'Configure automated prompt-based email/chat replies and flowcharts for your common user inquiries and support queue.',
    price: 59.99,
    estimated_time: '3 hours'
  }
]

// Default mock jobs
const MOCK_JOBS: FreelanceJob[] = [
  {
    id: 'job-101',
    template_id: 'template-qa',
    task_type: 'QA Testing Run',
    customer_email: 'alex@techstartup.io',
    details: 'Run the Cypress test suite against our staging build and send the screenshot outputs.',
    amount_paid: 49.99,
    status: 'delivered',
    created_at: '2026-07-01T10:15:30Z',
    summary: 'Automated test suite successfully executed with 48/50 tests passing. Detected a minor CSS alignment issue on the landing page checkout button.',
    deliverables: ['qa_run_report_101.pdf', 'cypress_screenshots.zip']
  },
  {
    id: 'job-102',
    template_id: 'template-copywriting',
    task_type: 'Technical Copywriting',
    customer_email: 'marketing@devtools.com',
    details: 'Write a 1200-word blog post about the benefits of local-first AI models in software development.',
    amount_paid: 29.99,
    status: 'completed',
    created_at: '2026-07-04T14:22:10Z',
    summary: 'Completed high-converting 1250-word technical blog post covering lightweight LLMs, local offline latency benefits, and secure data compliance.',
    deliverables: ['local_first_ai_post.md']
  },
  {
    id: 'job-103',
    template_id: 'template-scraping',
    task_type: 'Web Data Scraping',
    customer_email: 'research@unidata.org',
    details: 'Scrape the list of top AI research institutions from the CS Rankings directory.',
    amount_paid: 39.99,
    status: 'processing',
    created_at: '2026-07-06T08:05:00Z',
    summary: 'Currently traversing page indices and extracting institution records...'
  }
]

const loadPersistedJobs = (): FreelanceJob[] => {
  try {
    const jobsStr = localStorage.getItem('jarvis-freelance-jobs')
    if (jobsStr) {
      return JSON.parse(jobsStr)
    }
  } catch (e) {
    console.error('Failed to parse persisted jobs:', e)
  }
  // Initialize with MOCK_JOBS if none are persisted
  localStorage.setItem('jarvis-freelance-jobs', JSON.stringify(MOCK_JOBS))
  return MOCK_JOBS
}

const persistJobs = (jobs: FreelanceJob[]) => {
  localStorage.setItem('jarvis-freelance-jobs', JSON.stringify(jobs))
}

const calculateEarnings = (jobs: FreelanceJob[]) => {
  const completedOrDelivered = jobs.filter((j) => j.status === 'completed' || j.status === 'delivered')
  const total_earned = completedOrDelivered.reduce((sum, j) => sum + j.amount_paid, 0)
  return {
    total_earned: parseFloat(total_earned.toFixed(2)),
    completed_jobs: completedOrDelivered.length
  }
}

export const useFreelanceStore = create<FreelanceState>((set, get) => ({
  templates: MOCK_TEMPLATES,
  jobs: [],
  activeJob: null,
  isProcessing: false,
  isLoading: false,
  error: null,
  earnings: { total_earned: 0, completed_jobs: 0 },

  fetchTemplates: async () => {
    set({ isLoading: true, error: null })
    try {
      const token = useAuthStore.getState().token
      const response = await fetch(`${API_URL}/api/v1/freelance/templates`, {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('API failed or returned error status')
      }

      const data = await response.json()
      // Accept direct array or wrap if items key is present
      const templates = Array.isArray(data) ? data : (data.items || MOCK_TEMPLATES)
      set({ templates, isLoading: false })
    } catch (err: any) {
      console.warn('fetchTemplates failed, falling back to mock templates:', err.message)
      set({ templates: MOCK_TEMPLATES, isLoading: false })
    }
  },

  createOrder: async (templateId, details) => {
    set({ isProcessing: true, error: null })
    try {
      const token = useAuthStore.getState().token
      const response = await fetch(`${API_URL}/api/v1/freelance/order`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          template_id: templateId || null,
          customer_email: details.customer_email,
          customer_name: details.customer_name || null,
          description: details.specific_instructions
        })
      })

      if (!response.ok) {
        throw new Error('Failed to create order on backend')
      }

      const data = await response.json()
      
      // Update local state with returned order/job
      const currentJobs = get().jobs
      const newJob: FreelanceJob = {
        id: data.job_id || data.id || `job-${Math.floor(Math.random() * 1000) + 200}`,
        template_id: templateId || '',
        task_type: data.template_name || (templateId ? (get().templates.find((t) => t.id === templateId)?.name || 'Custom Freelance Task') : 'Custom Freelance Task'),
        customer_email: details.customer_email,
        details: details.specific_instructions,
        amount_paid: data.amount_dollars || (data.amount_cents ? data.amount_cents / 100 : 0) || (templateId ? (get().templates.find((t) => t.id === templateId)?.price || 0) : 10.00),
        status: data.status || 'paid',
        created_at: data.created_at || new Date().toISOString(),
        payment_url: data.stripe_payment_link || data.payment_url || `https://checkout.stripe.com/pay/mock_session_${Math.floor(Math.random() * 100000)}`
      }

      const updatedJobs = [newJob, ...currentJobs]
      persistJobs(updatedJobs)
      set({
        jobs: updatedJobs,
        activeJob: newJob,
        earnings: calculateEarnings(updatedJobs),
        isProcessing: false
      })
      return newJob
    } catch (err: any) {
      console.warn('createOrder failed, creating local order with Stripe link fallback:', err.message)
      
      const currentJobs = get().jobs
      const template = templateId ? get().templates.find((t) => t.id === templateId) : null
      const estimatedPrice = template ? template.price : 10.00
      const newMockJob: FreelanceJob = {
        id: `job-${Math.floor(Math.random() * 1000) + 200}`,
        template_id: templateId || '',
        task_type: template?.name || 'Custom Freelance Task',
        customer_email: details.customer_email,
        details: details.specific_instructions,
        amount_paid: estimatedPrice,
        status: 'paid', // Start as paid in local mock mode to bypass real paywall
        created_at: new Date().toISOString(),
        payment_url: `https://checkout.stripe.com/pay/mock_session_${Math.floor(Math.random() * 100000)}`
      }

      const updatedJobs = [newMockJob, ...currentJobs]
      persistJobs(updatedJobs)
      set({
        jobs: updatedJobs,
        activeJob: newMockJob,
        earnings: calculateEarnings(updatedJobs),
        isProcessing: false
      })
      return newMockJob
    }
  },

  fetchJobs: async () => {
    set({ isLoading: true, error: null })
    try {
      const token = useAuthStore.getState().token
      const response = await fetch(`${API_URL}/api/v1/freelance/jobs`, {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch jobs')
      }

      const data = await response.json()
      const jobs = Array.isArray(data) ? data : (data.items || loadPersistedJobs())
      persistJobs(jobs)
      set({
        jobs,
        earnings: calculateEarnings(jobs),
        isLoading: false
      })
    } catch (err: any) {
      console.warn('fetchJobs failed, falling back to persisted local jobs:', err.message)
      const jobs = loadPersistedJobs()
      set({
        jobs,
        earnings: calculateEarnings(jobs),
        isLoading: false
      })
    }
  },

  fetchJob: async (id: string) => {
    set({ isLoading: true, error: null })
    try {
      const token = useAuthStore.getState().token
      const response = await fetch(`${API_URL}/api/v1/freelance/jobs/${id}`, {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch job details')
      }

      const data = await response.json()
      set({ activeJob: data, isLoading: false })
    } catch (err: any) {
      console.warn(`fetchJob for ${id} failed, falling back to local search:`, err.message)
      const currentJobs = get().jobs
      const job = currentJobs.find((j) => j.id === id) || null
      set({ activeJob: job, isLoading: false })
    }
  }
}))
