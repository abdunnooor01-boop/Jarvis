import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useAuthStore } from '../stores/auth';
import { colors, borderRadius, fontSize, spacing } from '../utils/theme';

const LoginScreen = () => {
  const { login, register, isLoading, error, clearError } = useAuthStore();
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');

  const handleSubmit = async () => {
    clearError();
    try {
      if (isLogin) {
        await login(email, password);
      } else {
        await register(email, password, displayName);
      }
    } catch (err: any) {
      Alert.alert('Error', err.detail || 'An error occurred');
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <View style={styles.content}>
        <View style={styles.header}>
          <Text style={styles.title}>Jarvis</Text>
          <Text style={styles.subtitle}>
            {isLogin ? 'Welcome Back' : 'Create Account'}
          </Text>
        </View>

        <View style={styles.form}>
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Email</Text>
            <TextInput
              style={styles.input}
              value={email}
              onChangeText={setEmail}
              placeholder="you@example.com"
              placeholderTextColor={colors.slate[400]}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
            />
          </View>

          {!isLogin && (
            <View style={styles.inputGroup}>
              <Text style={styles.label}>Display Name</Text>
              <TextInput
                style={styles.input}
                value={displayName}
                onChangeText={setDisplayName}
                placeholder="Your Name"
                placeholderTextColor={colors.slate[400]}
                autoCapitalize="words"
              />
            </View>
          )}

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Password</Text>
            <TextInput
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              placeholder="Enter your password"
              placeholderTextColor={colors.slate[400]}
              secureTextEntry
            />
          </View>

          {error && (
            <Text style={styles.errorText}>{error}</Text>
          )}

          <TouchableOpacity
            style={[styles.button, isLoading && styles.buttonDisabled]}
            onPress={handleSubmit}
            disabled={isLoading}
          >
            {isLoading ? (
              <ActivityIndicator color={colors.white} />
            ) : (
              <Text style={styles.buttonText}>
                {isLogin ? 'Login' : 'Sign Up'}
              </Text>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.switchButton}
            onPress={() => {
              setIsLogin(!isLogin);
              clearError();
            }}
          >
            <Text style={styles.switchText}>
              {isLogin
                ? "Don't have an account? Sign up"
                : 'Already have an account? Login'}
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.slate[50],
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: spacing['2xl'],
  },
  header: {
    alignItems: 'center',
    marginBottom: spacing['3xl'],
  },
  title: {
    fontSize: fontSize['3xl'],
    fontWeight: '700',
    color: colors.indigo[600],
    marginBottom: spacing.xs,
  },
  subtitle: {
    fontSize: fontSize.lg,
    color: colors.slate[600],
  },
  form: {
    backgroundColor: colors.white,
    borderRadius: borderRadius['2xl'],
    padding: spacing['2xl'],
    shadowColor: colors.black,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 4,
    borderWidth: 1,
    borderColor: colors.slate[200],
  },
  inputGroup: {
    marginBottom: spacing.lg,
  },
  label: {
    fontSize: fontSize.xs,
    fontWeight: '600',
    color: colors.slate[500],
    textTransform: 'uppercase',
    marginBottom: spacing.xs,
  },
  input: {
    backgroundColor: colors.slate[50],
    borderWidth: 1,
    borderColor: colors.slate[200],
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    fontSize: fontSize.md,
    color: colors.slate[900],
  },
  button: {
    backgroundColor: colors.indigo[600],
    borderRadius: borderRadius.lg,
    paddingVertical: spacing.md,
    alignItems: 'center',
    marginTop: spacing.md,
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonText: {
    color: colors.white,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
  switchButton: {
    marginTop: spacing.lg,
    alignItems: 'center',
  },
  switchText: {
    color: colors.indigo[600],
    fontSize: fontSize.sm,
  },
  errorText: {
    color: colors.red[500],
    fontSize: fontSize.sm,
    marginBottom: spacing.sm,
    textAlign: 'center',
  },
});

export default LoginScreen;