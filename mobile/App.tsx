import React, { useEffect } from 'react';
import { View, Text, ActivityIndicator, StyleSheet, StatusBar } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { useAuthStore } from './src/stores/auth';
import { useSettingsStore } from './src/stores/settings';
import { useChatStore } from './src/stores/chat';
import wsService from './src/services/websocket';
import AppNavigator, { navigationRef } from './src/navigation/AppNavigator';
import LoginScreen from './src/screens/LoginScreen';
import { colors } from './src/utils/theme';
import { registerForPushNotificationsAsync, setupNotifications } from './src/services/notifications';

const AppContent = () => {
  const { isAuthenticated, isLoading, initialize } = useAuthStore();
  const { loadSettings } = useSettingsStore();

  useEffect(() => {
    const init = async () => {
      await loadSettings();
      await initialize();
    };
    init();
  }, []);

  // Connect WebSocket when authenticated
  useEffect(() => {
    if (isAuthenticated) {
      wsService.connect();
      registerForPushNotificationsAsync();
      const unsubNotifications = setupNotifications(navigationRef);
      return unsubNotifications;
    } else {
      wsService.disconnect();
    }
  }, [isAuthenticated]);

  // Handle WebSocket messages for chat
  useEffect(() => {
    if (!isAuthenticated) return;
    const unsub = wsService.on('message', (data) => {
      if (data.type === 'message' && data.id && data.content) {
        useChatStore.getState().addMessage(
          useChatStore.getState().currentConversationId || '',
          {
            id: data.id,
            role: 'assistant',
            content: data.content,
            created_at: new Date().toISOString(),
          },
        );
      } else if (data.type === 'stream_start') {
        useChatStore.getState().setStreaming(true);
      } else if (data.type === 'done') {
        useChatStore.getState().setStreaming(false);
      }
    });
    return unsub;
  }, [isAuthenticated]);

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={colors.indigo[600]} />
        <Text style={styles.loadingText}>Starting Jarvis...</Text>
      </View>
    );
  }

  if (!isAuthenticated) {
    return <LoginScreen />;
  }

  return <AppNavigator />;
};

const App = () => {
  return (
    <SafeAreaProvider>
      <StatusBar
        barStyle="dark-content"
        backgroundColor={colors.white}
      />
      <AppContent />
    </SafeAreaProvider>
  );
};

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.slate[950],
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
    color: colors.slate[400],
  },
});

export default App;