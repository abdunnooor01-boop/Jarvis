import {
  User,
  AuthResponse,
  Message,
  Conversation,
  TaskTemplate,
  FreelanceJob,
  KnowledgeEntry,
  KnowledgeDigest,
  KnowledgeSource,
  Plugin,
  TaskPlan,
  TaskStep,
  TestPlan,
  TestRun,
  TestingSubscription
} from './types'

export class ApiClient {
  private baseUrl: string
  private token: string | null = null

  constructor(baseUrl: string = 'http://localhost:8000') {
    this.baseUrl = baseUrl
  }

  /**
   * Sets the base URL for API requests.
   */
  setBaseUrl(url: string) {
    this.baseUrl = url
  }

  /**
   * Gets the current base URL.
   */
  getBaseUrl(): string {
    return this.baseUrl
  }

  /**
   * Sets the authentication token.
   */
  setToken(token: string | null) {
    this.token = token
  }

  /**
   * Resolves the WebSocket URL corresponding to the current HTTP baseUrl.
   */
  getWebSocketUrl(path: string = '/ws/v1/chat'): string {
    const wsProtocol = this.baseUrl.startsWith('https') ? 'wss:' : 'ws:'
    const urlWithoutProtocol = this.baseUrl.replace(/^https?:\/\//, '')
    return `${wsProtocol}//${urlWithoutProtocol}${path}`
  }

  /**
   * Base request helper.
   */
  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${path}`
    const headers = new Headers(options.headers)

    if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json')
    }

    if (this.token) {
      headers.set('Authorization', `Bearer ${this.token}`)
    }

    const response = await fetch(url, {
      ...options,
      headers
    })

    if (!response.ok) {
      let errorMessage = `API Request failed with status ${response.status}`
      try {
        const errorData = await response.json()
        if (errorData?.detail) {
          errorMessage = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail)
        }
      } catch {
        // Fallback to default message
      }
      throw new Error(errorMessage)
    }

    try {
      return await response.json() as T
    } catch {
      return {} as T
    }
  }

  // --- Auth API ---
  async getProfile(): Promise<User> {
    return this.request<User>('/api/v1/auth/profile')
  }

  // --- Chat API ---
  async fetchConversations(): Promise<Conversation[]> {
    return this.request<Conversation[]>('/api/v1/chat/conversations')
  }

  async fetchMessages(conversationId: string): Promise<Message[]> {
    return this.request<Message[]>(`/api/v1/chat/conversations/${conversationId}/messages`)
  }

  // --- Knowledge API ---
  async fetchKnowledgeEntries(search?: string): Promise<KnowledgeEntry[] | { items: KnowledgeEntry[] }> {
    const query = search ? `?search=${encodeURIComponent(search)}` : ''
    return this.request<KnowledgeEntry[] | { items: KnowledgeEntry[] }>(`/api/v1/knowledge/entries${query}`)
  }

  async fetchKnowledgeDigest(): Promise<KnowledgeDigest> {
    return this.request<KnowledgeDigest>('/api/v1/knowledge/digest')
  }

  async fetchKnowledgeSources(): Promise<KnowledgeSource[] | { items: KnowledgeSource[] }> {
    return this.request<KnowledgeSource[] | { items: KnowledgeSource[] }>('/api/v1/knowledge/sources')
  }

  async refreshKnowledgeSource(id: string): Promise<any> {
    return this.request<any>(`/api/v1/knowledge/crawl/${id}`, { method: 'POST' })
  }

  async markKnowledgeEntryRead(id: string): Promise<any> {
    return this.request<any>(`/api/v1/knowledge/entries/${id}/read`, { method: 'POST' })
  }

  // --- Freelance API ---
  async fetchFreelanceTemplates(): Promise<TaskTemplate[] | { items: TaskTemplate[] }> {
    return this.request<TaskTemplate[] | { items: TaskTemplate[] }>('/api/v1/freelance/templates')
  }

  async fetchFreelanceJobs(): Promise<FreelanceJob[] | { items: FreelanceJob[] }> {
    return this.request<FreelanceJob[] | { items: FreelanceJob[] }>('/api/v1/freelance/jobs')
  }

  async fetchFreelanceJob(id: string): Promise<FreelanceJob> {
    return this.request<FreelanceJob>(`/api/v1/freelance/jobs/${id}`)
  }

  async createFreelanceOrder(details: {
    template_id: string | null
    customer_email: string
    customer_name?: string | null
    description: string
  }): Promise<FreelanceJob> {
    return this.request<FreelanceJob>('/api/v1/freelance/order', {
      method: 'POST',
      body: JSON.stringify(details)
    })
  }

  // --- Plugins API ---
  async fetchPlugins(): Promise<Plugin[]> {
    return this.request<Plugin[]>('/api/v1/plugins')
  }

  async togglePlugin(name: string): Promise<Plugin> {
    return this.request<Plugin>(`/api/v1/plugins/${name}/toggle`, { method: 'POST' })
  }

  // --- Tasks API ---
  async fetchTaskPlans(): Promise<TaskPlan[] | { items: TaskPlan[] }> {
    return this.request<TaskPlan[] | { items: TaskPlan[] }>('/api/v1/tasks')
  }

  async createTaskPlan(goal: string): Promise<TaskPlan> {
    return this.request<TaskPlan>('/api/v1/tasks/plan', {
      method: 'POST',
      body: JSON.stringify({ goal })
    })
  }

  async executeTaskPlan(id: string): Promise<any> {
    return this.request<any>(`/api/v1/tasks/plan/${id}/execute`, { method: 'POST' })
  }

  async pauseTaskPlan(id: string): Promise<any> {
    return this.request<any>(`/api/v1/tasks/plan/${id}/pause`, { method: 'POST' })
  }

  async resumeTaskPlan(id: string): Promise<any> {
    return this.request<any>(`/api/v1/tasks/plan/${id}/resume`, { method: 'POST' })
  }

  async cancelTaskPlan(id: string): Promise<any> {
    return this.request<any>(`/api/v1/tasks/plan/${id}/cancel`, { method: 'POST' })
  }

  // --- Testing API ---
  async fetchTestPlans(): Promise<TestPlan[] | { items: TestPlan[] }> {
    return this.request<TestPlan[] | { items: TestPlan[] }>('/api/v1/testing/plans')
  }

  async createTestPlan(plan: Omit<TestPlan, 'id' | 'created_at' | 'status' | 'last_run_at' | 'pass_rate'> & { id?: string }): Promise<TestPlan> {
    return this.request<TestPlan>('/api/v1/testing/plans', {
      method: 'POST',
      body: JSON.stringify(plan)
    })
  }

  async triggerTestRun(planId: string): Promise<TestRun> {
    return this.request<TestRun>(`/api/v1/testing/plans/${planId}/run`, { method: 'POST' })
  }

  async fetchTestRuns(): Promise<TestRun[] | { items: TestRun[] }> {
    return this.request<TestRun[] | { items: TestRun[] }>('/api/v1/testing/runs')
  }

  async fetchTestRunDetail(runId: string): Promise<TestRun> {
    return this.request<TestRun>(`/api/v1/testing/runs/${runId}`)
  }

  async fetchTestingSubscription(): Promise<TestingSubscription> {
    return this.request<TestingSubscription>('/api/v1/testing/subscription')
  }
}

// Export a default shared instance
export const api = new ApiClient()
