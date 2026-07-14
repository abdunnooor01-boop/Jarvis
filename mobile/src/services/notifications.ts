/**
 * Push Notification Service
 * Handles push notification registration and handling using expo-notifications
 */
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { Platform } from 'react-native';
import api from './api';

// Configure notification handler
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export interface PushNotificationData {
  type: string;
  title?: string;
  body?: string;
  data?: Record<string, any>;
}

class PushNotificationService {
  private expoPushToken: string | null = null;
  private notificationListeners: Array<() => void> = [];
  private _initialized = false;

  async initialize(): Promise<void> {
    if (this._initialized) return;

    try {
      // Request permissions
      const { status: existingStatus } = await Notifications.getPermissionsAsync();
      let finalStatus = existingStatus;

      if (existingStatus !== 'granted') {
        const { status } = await Notifications.requestPermissionsAsync();
        finalStatus = status;
      }

      if (finalStatus !== 'granted') {
        console.warn('Push notification permissions not granted');
        return;
      }

      // Get Expo push token
      const tokenData = await Notifications.getExpoPushTokenAsync();
      this.expoPushToken = tokenData.data;

      // Register token with backend
      await this.registerTokenWithBackend(this.expoPushToken);

      // Android-specific notification channel
      if (Platform.OS === 'android') {
        await Notifications.setNotificationChannelAsync('default', {
          name: 'Default',
          importance: Notifications.AndroidImportance.MAX,
          vibrationPattern: [0, 250, 250, 250],
          lightColor: '#4f46e5',
        });
      }

      this._initialized = true;
    } catch (error) {
      console.warn('Failed to initialize push notifications:', error);
    }
  }

  private async registerTokenWithBackend(token: string): Promise<void> {
    try {
      await api.registerPushToken(token);
    } catch {
      // Token registration will be retried on next app start
      console.warn('Failed to register push token with backend');
    }
  }

  async unregister(): Promise<void> {
    if (this.expoPushToken) {
      try {
        await api.unregisterPushToken(this.expoPushToken);
      } catch {
        // Ignore unregister errors
      }
      this.expoPushToken = null;
    }
  }

  getPushToken(): string | null {
    return this.expoPushToken;
  }

  // Listen for incoming notifications when app is foregrounded
  addNotificationReceivedListener(handler: (notification: Notifications.Notification) => void): () => void {
    const subscription = Notifications.addNotificationReceivedListener(handler);
    this.notificationListeners.push(() => subscription.remove());
    return () => subscription.remove();
  }

  // Listen for notification taps (user opened notification)
  addNotificationResponseListener(handler: (response: Notifications.NotificationResponse) => void): () => void {
    const subscription = Notifications.addNotificationResponseListener(handler);
    this.notificationListeners.push(() => subscription.remove());
    return () => subscription.remove();
  }

  // Get the last notification that caused the app to open
  async getLastNotificationResponse(): Promise<Notifications.NotificationResponse | null> {
    return Notifications.getLastNotificationResponseAsync();
  }

  // Schedule a local notification
  async scheduleLocalNotification(title: string, body: string, data?: Record<string, any>): Promise<string> {
    const id = await Notifications.scheduleNotificationAsync({
      content: {
        title,
        body,
        data,
        sound: true,
      },
      trigger: null, // Immediately
    });
    return id;
  }

  cleanup(): void {
    this.notificationListeners.forEach((remove) => remove());
    this.notificationListeners = [];
  }
}

export const pushNotificationService = new PushNotificationService();
export default pushNotificationService;