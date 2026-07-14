import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../services/api';

interface SettingsState {
  apiUrl: string;
  wsUrl: string;
  theme: 'light' | 'dark' | 'system';
  fontSize: 'small' | 'medium' | 'large';
  loadSettings: () => Promise<void>;
  setApiUrl: (url: string) => Promise<void>;
  setTheme: (theme: 'light' | 'dark' | 'system') => Promise<void>;
  setFontSize: (size: 'small' | 'medium' | 'large') => Promise<void>;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  apiUrl: 'http://localhost:8000',
  wsUrl: 'ws://localhost:8000/ws/v1/chat',
  theme: 'system',
  fontSize: 'medium',

  loadSettings: async () => {
    try {
      const apiUrl = await AsyncStorage.getItem('jarvis_api_url');
      const theme = await AsyncStorage.getItem('jarvis_theme');
      const fontSize = await AsyncStorage.getItem('jarvis_font_size');
      if (apiUrl) {
        api.setBaseUrl(apiUrl);
        set({ apiUrl });
      }
      if (theme) set({ theme: theme as any });
      if (fontSize) set({ fontSize: fontSize as any });
    } catch {
      // Use defaults
    }
  },

  setApiUrl: async (url: string) => {
    api.setBaseUrl(url);
    await AsyncStorage.setItem('jarvis_api_url', url);
    set({ apiUrl: url });
  },

  setTheme: async (theme: 'light' | 'dark' | 'system') => {
    await AsyncStorage.setItem('jarvis_theme', theme);
    set({ theme });
  },

  setFontSize: async (fontSize: 'small' | 'medium' | 'large') => {
    await AsyncStorage.setItem('jarvis_font_size', fontSize);
    set({ fontSize });
  },
}));