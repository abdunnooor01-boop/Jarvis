/**
 * API type definitions matching the backend schemas
 */

// Auth types
export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  display_name: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
  display_name: string;
  created_at: string;
}

// Chat types
export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string;
  messages: Message[];
  created_at: string;
  updated_at: string;
}

export interface ConversationCreate {
  title?: string;
}

// Knowledge types
export interface KnowledgeEntry {
  id: string;
  title: string;
  url: string;
  summary: string;
  content: string;
  source: string;
  category: string;
  tags: string[];
  read: boolean;
  created_at: string;
}

export interface DigestEntry {
  id: string;
  title: string;
  summary: string;
  category: string;
  importance: string;
  created_at: string;
}

export interface DigestResponse {
  generated_at: string;
  total_entries: number;
  entries: DigestEntry[];
}

// Testing types
export interface TestPlan {
  id: string;
  name: string;
  url: string;
  status: string;
  total_tests?: number;
  passed?: number;
  failed?: number;
  pass_rate?: number | null;
  schedule?: string;
  test_criteria?: string;
  created_at: string;
  updated_at: string;
}

export interface TestStepResult {
  id: string;
  name: string;
  status: 'passed' | 'failed' | 'pending';
  error?: string | null;
  duration?: number;
}

export interface TestRun {
  id: string;
  plan_id: string;
  plan_url?: string;
  url: string;
  name: string;
  status: 'passed' | 'failed' | 'running' | 'queued';
  passed_count: number;
  failed_count: number;
  duration: number; // in seconds
  summary?: string;
  error_message?: string;
  created_at: string;
  screenshots?: string[];
  results?: TestStepResult[];
}

// Freelance types
export interface TaskTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  price_cents: number;
  estimated_minutes: number;
}

export interface FreelanceJob {
  id: string;
  template_id: string;
  template_name: string;
  status: string;
  params: Record<string, any>;
  result?: Record<string, any>;
  price_cents: number;
  created_at: string;
  completed_at?: string;
}

// Plugin types
export interface Plugin {
  id: string;
  name: string;
  description: string;
  version: string;
  enabled: boolean;
  author: string;
  settings: Record<string, any>;
}

// WebSocket message types
export interface WSMessage {
  type: string;
  content?: string;
  conversation_id?: string;
  id?: string;
  token?: string;
}

export interface WSAuthMessage extends WSMessage {
  type: 'auth';
  token: string;
}

export interface WSChatMessage extends WSMessage {
  type: 'message';
  conversation_id: string;
  content: string;
}

export interface WSAssistantMessage extends WSMessage {
  type: 'message';
  id: string;
  content: string;
}

export interface WSStreamStart extends WSMessage {
  type: 'stream_start';
}

export interface WSDone extends WSMessage {
  type: 'done';
}

// Knowledge Source types
export interface KnowledgeSource {
  id: string;
  name: string;
  url: string | null;
  category?: string;
  source_type?: string;
  last_fetched_at: string | null;
  is_active: boolean;
  created_at?: string;
}

// Device Token / Notifications types
export interface DeviceTokenRegisterRequest {
  token: string;
  platform: string;
  device_name?: string | null;
}

export interface DeviceTokenResponse {
  id: string;
  token: string;
  platform: string;
  device_name?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface NotificationPreferences {
  test_run_completed: boolean;
  knowledge_digest_ready: boolean;
  freelance_task_assigned: boolean;
  new_message: boolean;
}

// Testing Subscription types
export interface TestingSubscription {
  id: string;
  customer_id: string;
  tier: string;
  status: string;
  runs_used: number;
  runs_limit: number;
  is_active: boolean;
  stripe_subscription_id?: string | null;
  stripe_customer_id?: string | null;
  current_period_start?: string | null;
  current_period_end?: string | null;
  created_at: string;
  updated_at: string;
  stripe_checkout_url?: string | null;
}
