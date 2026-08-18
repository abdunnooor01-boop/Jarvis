/**
 * Backend API helpers.
 *
 * URL strategy (lead requirement):
 *  - WEB build (page served over http/https): use RELATIVE paths (/api/v1/...).
 *    The :3000 web server proxies /api and /ws to the backend on :8000, so a
 *    relative path always reaches the right backend from any host. NEVER fall
 *    back to http://localhost:8000 in the browser — that would point at the
 *    USER's own machine.
 *  - Electron desktop build (renderer served from file://): use the full
 *    backend URL from window.api.getBackendUrlSync().
 */
export interface AuthResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface MeResponse {
  id: string
  email: string
  display_name: string
  created_at: string
}

export interface ConversationSummary {
  id: string
  title: string
}
/** A single message as returned by the conversation-detail endpoint. */
export interface MessageHistoryItem {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string
}
/** Full conversation including its message history. */
export interface ConversationDetail {
  id: string
  title: string
  messages: MessageHistoryItem[]
  created_at: string
  updated_at: string
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Resolve the API base: '' (relative) in web, full origin in Electron. */
function apiBase(): string {
  const proto = typeof window !== 'undefined' ? window.location.protocol : 'http:'
  if (proto === 'http:' || proto === 'https:') {
    // Web build — same-origin, proxied by the :3000 server.
    return ''
  }
  // Electron — renderer is served from file://; ask the preload for the
  // configured backend URL.
  // @ts-ignore
  if (window.api && typeof window.api.getBackendUrlSync === 'function') {
    // @ts-ignore
    const url = window.api.getBackendUrlSync()
    if (url) return url
  }
  return ''
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${apiBase()}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  let data: any = null
  try {
    data = await res.json()
  } catch {
    // No JSON body — fall through
  }
  if (!res.ok) {
    const detail = data && (data.detail || data.message)
    const message = typeof detail === 'string' && detail
      ? detail
      : `Request failed (${res.status})`
    throw new ApiError(res.status, message)
  }
  return data as T
}

export function login(email: string, password: string): Promise<AuthResponse> {
  return apiFetch<AuthResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export function register(
  email: string,
  password: string,
  displayName: string
): Promise<AuthResponse> {
  return apiFetch<AuthResponse>('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, display_name: displayName }),
  })
}

export function getMe(token: string): Promise<MeResponse> {
  return apiFetch<MeResponse>('/api/v1/auth/me', {
    headers: { Authorization: `Bearer ${token}` },
  })
}

export function fetchConversations(token: string): Promise<ConversationSummary[]> {
  return apiFetch<ConversationSummary[]>('/api/v1/chat/conversations', {
    headers: { Authorization: `Bearer ${token}` },
  })
}
/** Fetch a single conversation including its full message history. */
export function fetchConversationDetail(
  conversationId: string,
  token: string
): Promise<ConversationDetail> {
  return apiFetch<ConversationDetail>(`/api/v1/chat/conversations/${conversationId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
}
