/**
 * Shared notification types for Jarvis mobile and desktop apps.
 *
 * These types are used by both the backend (for sending notifications)
 * and the frontend/mobile apps (for receiving and displaying them).
 */

/** Supported push notification event types */
export type NotificationEventType =
  | 'test_run_completed'
  | 'knowledge_digest_ready'
  | 'freelance_task_assigned'
  | 'new_message';

/** Device platform types */
export type DevicePlatform = 'ios' | 'android' | 'web' | 'desktop';

/** A push notification payload sent from the backend */
export interface NotificationPayload {
  event_type: NotificationEventType;
  title: string;
  body: string;
  data?: Record<string, string>;
  sent_at?: string;
}

/** A registered device token */
export interface DeviceToken {
  id: string;
  token: string;
  platform: DevicePlatform;
  device_name?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** User notification preferences */
export interface NotificationPreferences {
  test_run_completed: boolean;
  knowledge_digest_ready: boolean;
  freelance_task_assigned: boolean;
  new_message: boolean;
}

/** API request to register a device token */
export interface RegisterDeviceRequest {
  token: string;
  platform: DevicePlatform;
  device_name?: string;
}

/** API request to update notification preferences */
export interface UpdatePreferencesRequest {
  test_run_completed?: boolean;
  knowledge_digest_ready?: boolean;
  freelance_task_assigned?: boolean;
  new_message?: boolean;
}

/** Notification event type display labels */
export const NOTIFICATION_LABELS: Record<NotificationEventType, string> = {
  test_run_completed: 'Test Run Completed',
  knowledge_digest_ready: 'Knowledge Digest Ready',
  freelance_task_assigned: 'Freelance Task Assigned',
  new_message: 'New Message',
};

/** Notification event type icons (emoji) */
export const NOTIFICATION_ICONS: Record<NotificationEventType, string> = {
  test_run_completed: '✅',
  knowledge_digest_ready: '📚',
  freelance_task_assigned: '📋',
  new_message: '💬',
};