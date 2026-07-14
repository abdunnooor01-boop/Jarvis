/**
 * Theme system for Jarvis Mobile
 * Matches the desktop app's look: indigo accent, slate backgrounds, dark mode support
 */

export const colors = {
  // Primary indigo palette
  indigo: {
    50: '#eef2ff',
    100: '#e0e7ff',
    200: '#c7d2fe',
    300: '#a5b4fc',
    400: '#818cf8',
    500: '#6366f1',
    600: '#4f46e5',
    700: '#4338ca',
    800: '#3730a3',
    900: '#312e81',
    950: '#1e1b4b',
  },
  // Slate/gray palette
  slate: {
    50: '#f8fafc',
    100: '#f1f5f9',
    200: '#e2e8f0',
    300: '#cbd5e1',
    400: '#94a3b8',
    500: '#64748b',
    600: '#475569',
    700: '#334155',
    800: '#1e293b',
    900: '#0f172a',
    950: '#020617',
  },
  white: '#ffffff',
  black: '#000000',
  red: {
    50: '#fef2f2',
    100: '#fee2e2',
    400: '#f87171',
    500: '#ef4444',
    600: '#dc2626',
    700: '#b91c1c',
    950: '#450a0a',
  },
  green: {
    500: '#22c55e',
    600: '#16a34a',
  },
  emerald: {
    100: '#d1fae5',
    400: '#34d399',
    600: '#059669',
    700: '#047857',
  },
  amber: {
    500: '#f59e0b',
  },
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  '2xl': 24,
  '3xl': 32,
  '4xl': 40,
};

export const borderRadius = {
  sm: 6,
  md: 8,
  lg: 12,
  xl: 16,
  '2xl': 20,
  full: 9999,
};

export const fontSize = {
  xs: 10,
  sm: 12,
  md: 14,
  lg: 16,
  xl: 18,
  '2xl': 20,
  '3xl': 24,
};

export interface Theme {
  dark: boolean;
  colors: {
    background: string;
    surface: string;
    surfaceSecondary: string;
    text: string;
    textSecondary: string;
    textTertiary: string;
    border: string;
    primary: string;
    primaryLight: string;
    primaryDark: string;
    danger: string;
    success: string;
    warning: string;
    card: string;
    inputBackground: string;
    chatBubbleUser: string;
    chatBubbleAssistant: string;
    chatBubbleUserText: string;
    chatBubbleAssistantText: string;
  };
}

export const lightTheme: Theme = {
  dark: false,
  colors: {
    background: colors.white,
    surface: colors.slate[50],
    surfaceSecondary: colors.slate[100],
    text: colors.slate[900],
    textSecondary: colors.slate[600],
    textTertiary: colors.slate[400],
    border: colors.slate[200],
    primary: colors.indigo[600],
    primaryLight: colors.indigo[100],
    primaryDark: colors.indigo[700],
    danger: colors.red[500],
    success: colors.green[600],
    warning: colors.amber[500],
    card: colors.white,
    inputBackground: colors.slate[100],
    chatBubbleUser: colors.indigo[600],
    chatBubbleAssistant: colors.slate[100],
    chatBubbleUserText: colors.white,
    chatBubbleAssistantText: colors.slate[900],
  },
};

export const darkTheme: Theme = {
  dark: true,
  colors: {
    background: colors.slate[950],
    surface: colors.slate[900],
    surfaceSecondary: colors.slate[800],
    text: colors.slate[100],
    textSecondary: colors.slate[400],
    textTertiary: colors.slate[500],
    border: colors.slate[800],
    primary: colors.indigo[500],
    primaryLight: colors.indigo[900],
    primaryDark: colors.indigo[400],
    danger: colors.red[400],
    success: colors.green[500],
    warning: colors.amber[500],
    card: colors.slate[900],
    inputBackground: colors.slate[800],
    chatBubbleUser: colors.indigo[600],
    chatBubbleAssistant: colors.slate[800],
    chatBubbleUserText: colors.white,
    chatBubbleAssistantText: colors.slate[100],
  },
};