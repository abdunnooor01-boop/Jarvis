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
  total_tests: number;
  passed: number;
  failed: number;
  created_at: string;
  updated_at: string;
}

export interface TestRun {
  id: string;
  plan_id: string;
  url: string;
  name: string;
  status: string;
  total_tests: number;
  passed: number;
  failed: number;
  summary?: string;
  error_message?: string;
  results: TestResult[];
  created_at: string;
}

export interface TestResult {
  id: string;
  run_id: string;
  step_number: number;
  criterion: string;
  test_type: string;
  passed: boolean;
  detail?: string;
  screenshot_path?: string;
  duration_ms?: number;
}

// Freelance types
export interface TaskTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  price_cents: number;
  estimated_minutes: number;
  required_capabilities?: string[];
}

export interface FreelanceJob {
  id: string;
  template_id: string;
  template_name: string;
  status: string;
  params: Record<string, any>;
  result?: Record<string, any>;
  result_summary?: string;
  result_files?: Record<string, string>;
  price_cents: number;
  amount_cents?: number;
  amount_dollars?: number;
  customer_email?: string;
  customer_name?: string;
  description?: string;
  stripe_payment_link?: string | null;
  created_at: string;
  completed_at?: string;
  paid_at?: string;
}

export interface FreelanceOrderResponse {
  job_id: string;
  template_name?: string;
  amount_cents: number;
  amount_dollars: number;
  status: string;
  stripe_payment_link: string | null;
  message: string;
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
  installed_at?: string;
  tools?: string[];
}

// Language types
export interface LanguageInfo {
  code: string;
  name: string;
  native_name: string;
}

export interface LanguagesResponse {
  default: string;
  supported: LanguageInfo[];
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