import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import api from './api';

// Set standard foreground notification configuration
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  } as any),
});

/**
 * Request notification permissions and register the Expo push token with the backend.
 */
export async function registerForPushNotificationsAsync(): Promise<string | null> {
  if (Platform.OS === 'web') return null;

  try {
    const existingStatus = ((await Notifications.getPermissionsAsync()) as any).status;
    let finalStatus = existingStatus;
    if (existingStatus !== 'granted') {
      const { status } = (await Notifications.requestPermissionsAsync()) as any;
      finalStatus = status;
    }
    if (finalStatus !== 'granted') {
      console.log('Push notification permissions denied.');
      return null;
    }

    const tokenData = await Notifications.getExpoPushTokenAsync();
    const token = tokenData.data;

    // Register token with backend using api service
    await api.registerDeviceToken({
      token,
      platform: Platform.OS,
      device_name: Platform.OS === 'ios' ? 'iOS Device' : 'Android Device',
    });

    console.log('Push token successfully registered with backend:', token);

    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync('default', {
        name: 'default',
        importance: Notifications.AndroidImportance.MAX,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: '#4f46e5',
      });
    }

    return token;
  } catch (err) {
    console.error('Failed to register device token for push notifications:', err);
    return null;
  }
}

/**
 * Configure notification listeners for foreground and background tap response actions.
 */
export function setupNotifications(navigationRef: any) {
  // Listen for clicked notifications to route to relevant screens
  const responseSubscription = Notifications.addNotificationResponseReceivedListener(response => {
    try {
      const data = response.notification.request.content.data;
      console.log('Push Notification clicked with payload:', data);

      if (data && data.screen) {
        if (navigationRef.isReady()) {
          navigationRef.navigate(data.screen as any, data.params);
        } else {
          // Navigation container not ready yet, retry with small delay
          setTimeout(() => {
            if (navigationRef.isReady()) {
              navigationRef.navigate(data.screen as any, data.params);
            }
          }, 1000);
        }
      }
    } catch (err) {
      console.error('Error handling notification tap routing:', err);
    }
  });

  return () => {
    responseSubscription.remove();
  };
}
