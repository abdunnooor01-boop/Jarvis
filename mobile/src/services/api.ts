/**
 * API client for Jarvis backend
 * Handles HTTP requests, auth tokens, and base URL configuration
 */
import * as SecureStore from 'expo-secure-store';
import {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  UserResponse,
  Conversation,
  ConversationDetail,
  ConversationCreate,
  KnowledgeEntry,
  DigestResponse,
  TestPlan,
  TestRun,
  TaskTemplate,
  FreelanceJob,
  Plugin,
} from '../types/api';

// Default API URL - can be overridden via env or settings
const DEFAULT_API_URL = 'http://localhost:8000';
const API_PREFIX = '/api/v1';

// Token storage keys
const ACCESS_TOKEN_KEY = 'jarvis_access_token';
const REFRESH_TOKEN_KEY = 'jarvis_refresh_token';

class ApiClient {
  private baseUrl: string;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;

  constructor() {
    this.baseUrl = DEFAULT_API_URL;
  }

  setBaseUrl(url: string) {
    this.baseUrl = url.replace(/\/+$/, '');
  }

  getBaseUrl(): string {
    return this.baseUrl;
  }

  async loadTokens(): Promise<boolean> {
    try {
      const access = await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
      const refresh = await SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
      if (access) this.accessToken = access;
      if (refresh) this.refreshToken = refresh;
      return !!this.accessToken;
    } catch {
      return false;
    }
  }

  async saveTokens(tokens: TokenResponse): Promise<void> {
    this.accessToken = tokens.access_token;
    this.refreshToken = tokens.refresh_token;
    await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, tokens.access_token);
    await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, tokens.refresh_token);
  }

  async clearTokens(): Promise<void> {
    this.accessToken = null;
    this.refreshToken = null;
    await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
    await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
  }

  isAuthenticated(): boolean {
    return !!this.accessToken;
  }

  getAccessToken(): string | null {
    return this.accessToken;
  }

  private async request<T>(
    method: string,
    path: string,
    body?: Record<string, any>,
    auth: boolean = true,
  ): Promise<T> {
    const url = `${this.baseUrl}${API_PREFIX}${path}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (auth && this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }

    const response = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });

    // Handle 401 - try refreshing token
    if (response.status === 401 && this.refreshToken) {
      const refreshed = await this.refreshAccessToken();
      if (refreshed) {
        headers['Authorization'] = `Bearer ${this.accessToken}`;
        const retryResponse = await fetch(url, {
          method,
          headers,
          body: body ? JSON.stringify(body) : undefined,
        });
        if (!retryResponse.ok) {
          throw new ApiError(await retryResponse.json(), retryResponse.status);
        }
        return retryResponse.json();
      }
      // Refresh failed, clear tokens
      await this.clearTokens();
      throw new ApiError({ detail: 'Session expired' }, 401);
    }

    if (!response.ok) {
      throw new ApiError(await response.json(), response.status);
    }

    // 204 No Content
    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  private async refreshAccessToken(): Promise<boolean> {
    if (!this.refreshToken) return false;
    try {
      const response = await fetch(
        `${this.baseUrl}${API_PREFIX}/auth/refresh`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: this.refreshToken }),
        },
      );
      if (!response.ok) return false;
      const tokens: TokenResponse = await response.json();
      await this.saveTokens(tokens);
      return true;
    } catch {
      return false;
    }
  }

  // ==================== Auth ====================

  async login(data: LoginRequest): Promise<TokenResponse> {
    const tokens = await this.request<TokenResponse>(
      'POST',
      '/auth/login',
      data,
      false,
    );
    await this.saveTokens(tokens);
    return tokens;
  }

  async register(data: RegisterRequest): Promise<TokenResponse> {
    const tokens = await this.request<TokenResponse>(
      'POST',
      '/auth/register',
      data,
      false,
    );
    await this.saveTokens(tokens);
    return tokens;
  }

  async logout(): Promise<void> {
    try {
      await this.request('POST', '/auth/logout', { access_token: this.accessToken });
    } finally {
      await this.clearTokens();
    }
  }

  async getProfile(): Promise<UserResponse> {
    return this.request<UserResponse>('GET', '/auth/me');
  }

  // ==================== Chat ====================

  async listConversations(): Promise<Conversation[]> {
    return this.request<Conversation[]>('GET', '/chat/conversations');
  }

  async getConversation(id: string): Promise<ConversationDetail> {
    return this.request<ConversationDetail>('GET', `/chat/conversations/${id}`);
  }

  async createConversation(data?: ConversationCreate): Promise<Conversation> {
    return this.request<Conversation>('POST', '/chat/conversations', data || {});
  }

  async deleteConversation(id: string): Promise<void> {
    return this.request<void>('DELETE', `/chat/conversations/${id}`);
  }

  // ==================== Knowledge ====================

  async listKnowledgeEntries(): Promise<KnowledgeEntry[]> {
    return this.request<KnowledgeEntry[]>('GET', '/knowledge/entries');
  }

  async getDigest(hoursBack: number = 168): Promise<DigestResponse> {
    return this.request<DigestResponse>('GET', `/knowledge/digest?hours_back=${hoursBack}`);
  }

  async getKnowledgeStats(): Promise<Record<string, any>> {
    return this.request<Record<string, any>>('GET', '/knowledge/stats');
  }

  async getUnreadCount(): Promise<{ unread_count: number }> {
    return this.request<{ unread_count: number }>('GET', '/knowledge/unread-count');
  }

  // ==================== Testing ====================

  async listTestPlans(): Promise<TestPlan[]> {
    return this.request<TestPlan[]>('GET', '/testing/plans');
  }

  async getTestPlan(id: string): Promise<TestPlan> {
    return this.request<TestPlan>('GET', `/testing/plans/${id}`);
  }

  async listTestRuns(): Promise<TestRun[]> {
    return this.request<TestRun[]>('GET', '/testing/runs');
  }

  async getTestRun(id: string): Promise<TestRun> {
    return this.request<TestRun>('GET', `/testing/runs/${id}`);
  }

  // ==================== Freelance ====================

  async listTaskTemplates(): Promise<TaskTemplate[]> {
    return this.request<TaskTemplate[]>('GET', '/freelance/templates');
  }

  async listJobs(): Promise<FreelanceJob[]> {
    return this.request<FreelanceJob[]>('GET', '/freelance/jobs');
  }

  async createJob(templateId: string, params: Record<string, any>): Promise<FreelanceJob> {
    return this.request<FreelanceJob>('POST', '/freelance/jobs', {
      template_id: templateId,
      params,
    });
  }

  // ==================== Plugins ====================

  async listPlugins(): Promise<Plugin[]> {
    return this.request<Plugin[]>('GET', '/plugins');
  }

  async togglePlugin(id: string, enabled: boolean): Promise<Plugin> {
    return this.request<Plugin>('PATCH', `/plugins/${id}`, { enabled });
  }
}

export class ApiError extends Error {
  public status: number;
  public detail: string;

  constructor(body: any, status: number) {
    super(body?.detail || 'An error occurred');
    this.status = status;
    this.detail = body?.detail || 'An error occurred';
  }
}

// Singleton instance
export const api = new ApiClient();
export default api;