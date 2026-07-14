import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../services/api';

// Storage keys
const OFFLINE_QUEUE_KEY = 'jarvis_offline_queue';
const TASK_CACHE_KEY = 'jarvis_tasks_cache';

export interface QueuedTask {
  id: string;
  endpoint: string;
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: Record<string, any>;
  description: string;
  queuedAt: string;
}

export interface TaskStatus {
  id: string;
  type: string;
  status: 'queued' | 'in_progress' | 'completed' | 'failed';
  description: string;
  result?: Record<string, any>;
  error?: string;
  createdAt: string;
  completedAt?: string;
}

interface OfflineQueueState {
  // Queued tasks (pending submission)
  offlineQueue: QueuedTask[];
  // Fetched server-side task statuses
  serverTasks: TaskStatus[];
  isOnline: boolean;
  isSyncing: boolean;

  // Actions
  queueTask: (task: Omit<QueuedTask, 'id' | 'queuedAt'>) => Promise<void>;
  removeFromQueue: (id: string) => Promise<void>;
  syncQueue: () => Promise<void>;
  loadQueue: () => Promise<void>;
  saveQueue: () => Promise<void>;

  setServerTasks: (tasks: TaskStatus[]) => void;
  fetchServerTasks: () => Promise<void>;
  setOnline: (online: boolean) => void;
  setSyncing: (syncing: boolean) => void;
}

export const useOfflineQueueStore = create<OfflineQueueState>((set, get) => ({
  offlineQueue: [],
  serverTasks: [],
  isOnline: true,
  isSyncing: false,

  queueTask: async (task) => {
    const newTask: QueuedTask = {
      ...task,
      id: `offline_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      queuedAt: new Date().toISOString(),
    };
    set((state) => ({
      offlineQueue: [...state.offlineQueue, newTask],
    }));
    await get().saveQueue();

    // Try to submit immediately if online
    if (get().isOnline) {
      await get().syncQueue();
    }
  },

  removeFromQueue: async (id) => {
    set((state) => ({
      offlineQueue: state.offlineQueue.filter((t) => t.id !== id),
    }));
    await get().saveQueue();
  },

  syncQueue: async () => {
    const { offlineQueue, isSyncing } = get();
    if (offlineQueue.length === 0 || isSyncing) return;

    set({ isSyncing: true });
    const remaining: QueuedTask[] = [];

    for (const task of offlineQueue) {
      try {
        const response = await fetch(
          `${api.getBaseUrl()}/api/v1${task.endpoint}`,
          {
            method: task.method,
            headers: {
              'Content-Type': 'application/json',
              ...(api.getAccessToken()
                ? { Authorization: `Bearer ${api.getAccessToken()}` }
                : {}),
            },
            body: task.body ? JSON.stringify(task.body) : undefined,
          },
        );
        if (response.ok) {
          // Successfully submitted - don't add back to queue
          continue;
        }
        // Failed - keep in queue
        remaining.push(task);
      } catch {
        // Network error - keep in queue
        remaining.push(task);
      }
    }

    set({ offlineQueue: remaining, isSyncing: false });
    await get().saveQueue();

    // Refresh task list after sync
    await get().fetchServerTasks();
  },

  loadQueue: async () => {
    try {
      const stored = await AsyncStorage.getItem(OFFLINE_QUEUE_KEY);
      if (stored) {
        set({ offlineQueue: JSON.parse(stored) });
      }
    } catch {
      // Use default empty queue
    }
  },

  saveQueue: async () => {
    try {
      await AsyncStorage.setItem(
        OFFLINE_QUEUE_KEY,
        JSON.stringify(get().offlineQueue),
      );
    } catch {
      // Ignore save errors
    }
  },

  setServerTasks: (tasks) => set({ serverTasks: tasks }),

  fetchServerTasks: async () => {
    try {
      const response = await fetch(
        `${api.getBaseUrl()}/api/v1/tasks`,
        {
          headers: api.getAccessToken()
            ? { Authorization: `Bearer ${api.getAccessToken()}` }
            : {},
        },
      );
      if (response.ok) {
        const tasks = await response.json();
        set({ serverTasks: tasks });
        // Cache locally for offline viewing
        await AsyncStorage.setItem(TASK_CACHE_KEY, JSON.stringify(tasks));
      }
    } catch {
      // Try loading from cache
      try {
        const cached = await AsyncStorage.getItem(TASK_CACHE_KEY);
        if (cached) {
          set({ serverTasks: JSON.parse(cached) });
        }
      } catch {
        // No cached data
      }
    }
  },

  setOnline: (online) => {
    const wasOffline = !get().isOnline;
    set({ isOnline: online });
    // If we just came back online, sync the queue
    if (online && wasOffline) {
      get().syncQueue();
    }
  },

  setSyncing: (syncing) => set({ isSyncing: syncing }),
}));