import React, { useEffect } from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { NavigationContainer } from '@react-navigation/native';
import { View, Text, StyleSheet } from 'react-native';
import { colors, fontSize } from '../utils/theme';
import { useOfflineQueueStore } from '../stores/offlineQueue';
import ChatScreen from '../screens/ChatScreen';
import KnowledgeScreen from '../screens/KnowledgeScreen';
import TestingScreen from '../screens/TestingScreen';
import FreelanceScreen from '../screens/FreelanceScreen';
import PluginScreen from '../screens/PluginScreen';
import TaskQueueScreen from '../screens/TaskQueueScreen';
import SettingsScreen from '../screens/SettingsScreen';

const Tab = createBottomTabNavigator();

// Simple text-based tab icons
const TabIcon = ({ name, focused }: { name: string; focused: boolean }) => {
  const icons: Record<string, string> = {
    Chat: '💬',
    Knowledge: '📚',
    Tasks: '📋',
    Testing: '🔬',
    Freelance: '💼',
    Plugins: '🧩',
    Settings: '⚙️',
  };

  return (
    <View style={styles.iconContainer}>
      <Text style={[styles.icon, focused && styles.iconFocused]}>
        {icons[name] || '•'}
      </Text>
    </View>
  );
};

const AppNavigator = () => {
  const { loadQueue, setOnline } = useOfflineQueueStore();

  useEffect(() => {
    loadQueue();
    setOnline(true);
  }, []);

  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={({ route }) => ({
          tabBarIcon: ({ focused }) => (
            <TabIcon name={route.name} focused={focused} />
          ),
          tabBarActiveTintColor: colors.indigo[600],
          tabBarInactiveTintColor: colors.slate[400],
          tabBarStyle: styles.tabBar,
          tabBarLabelStyle: styles.tabLabel,
          headerShown: false,
        })}
      >
        <Tab.Screen name="Chat" component={ChatScreen} />
        <Tab.Screen name="Knowledge" component={KnowledgeScreen} />
        <Tab.Screen name="Tasks" component={TaskQueueScreen} />
        <Tab.Screen name="Testing" component={TestingScreen} />
        <Tab.Screen name="Freelance" component={FreelanceScreen} />
        <Tab.Screen name="Plugins" component={PluginScreen} />
        <Tab.Screen name="Settings" component={SettingsScreen} />
      </Tab.Navigator>
    </NavigationContainer>
  );
};

const styles = StyleSheet.create({
  tabBar: {
    backgroundColor: colors.white,
    borderTopColor: colors.slate[200],
    borderTopWidth: 1,
    paddingTop: 4,
    height: 60,
  },
  tabLabel: {
    fontSize: fontSize.xs,
    fontWeight: '500',
    marginBottom: 4,
  },
  iconContainer: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  icon: {
    fontSize: 20,
    opacity: 0.5,
  },
  iconFocused: {
    opacity: 1,
  },
});

export default AppNavigator;