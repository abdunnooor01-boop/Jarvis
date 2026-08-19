/**
 * Shared push-notification types — mirrors the backend
 * `notification` models (DeviceToken, NotificationEvent, preferences).
 * Consumed by the web and mobile clients for registration and rendering.
 */
export type NotificationEventType =
  | 'message'
  | 'task_completed'
  | 'task_failed'
  | 'freelance_job'
  | 'testing_run'
  | 'knowledge_digest'
  | 'system'

export interface NotificationPayload {
  id: string
  user_id: string
  type: NotificationEventType
  title: string
  body: string
  data?: Record<string, string>
  read?: boolean | null
  created_at: string
}

export interface DeviceToken {
  id: string
  user_id: string
  token: string
  platform: 'ios' | 'android' | 'web' | 'desktop' | 'unknown'
  device_name?: string | null
  is_active?: boolean | null
  created_at?: string | null
  updated_at?: string | null
}

export interface NotificationPreference {
  id: string
  user_id: string
  enabled_events: NotificationEventType[]
  created_at: string
  updated_at?: string | null
}