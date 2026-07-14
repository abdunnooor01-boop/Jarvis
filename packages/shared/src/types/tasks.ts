/**
 * Shared task queue types for Jarvis mobile and desktop apps.
 *
 * These types define the task queue API contract used by both
 * the backend (multitasking engine) and frontend/mobile clients.
 */

/** Status values for a queued task plan */
export type TaskPlanStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'partially_completed'
  | 'cancelled';

/** Status values for an individual task step */
export type TaskStepStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'skipped'
  | 'cancelled';

/** A single step within a task plan */
export interface TaskStep {
  id: string;
  step_number: number;
  description: string;
  tool_name: string;
  status: TaskStepStatus;
  result?: string;
  error?: string;
  started_at?: string;
  completed_at?: string;
}

/** A task plan in the queue */
export interface TaskQueueItem {
  id: string;
  goal: string;
  status: TaskPlanStatus;
  total_steps: number;
  completed_steps: number;
  failed_steps: number;
  is_running: boolean;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  steps?: TaskStep[];
}

/** Response from listing the task queue */
export interface TaskQueueListResponse {
  items: TaskQueueItem[];
  total: number;
}

/** Response from enqueuing a new task */
export interface TaskEnqueueResponse {
  plan_id: string;
  goal: string;
  status: string;
  total_steps: number;
  message: string;
  worker_pool: WorkerPoolStats;
}

/** Worker pool statistics */
export interface WorkerPoolStats {
  max_workers: number;
  active_plans: number;
  available_worker_slots: number;
  plan_ids: string[];
}

/** Request to enqueue a new task */
export interface EnqueueTaskRequest {
  goal: string;
}

/** Response from cancelling a task */
export interface CancelTaskResponse {
  plan_id: string;
  status: string;
  message: string;
}