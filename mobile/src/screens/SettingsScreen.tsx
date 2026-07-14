import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Alert,
  Switch,
  ActivityIndicator,
} from 'react-native';
import { useAuthStore } from '../stores/auth';
import { useSettingsStore } from '../stores/settings';
import api from '../services/api';
import { colors, borderRadius, fontSize, spacing } from '../utils/theme';

const SettingsScreen = () => {
  const { user, logout } = useAuthStore();
  const { apiUrl, theme, setApiUrl, setTheme } = useSettingsStore();
  const [urlInput, setUrlInput] = useState(apiUrl);
  const [saving, setSaving] = useState(false);

  // Notification preferences states
  const [prefTestRun, setPrefTestRun] = useState(true);
  const [prefDigest, setPrefDigest] = useState(true);
  const [prefFreelance, setPrefFreelance] = useState(true);
  const [prefMessage, setPrefMessage] = useState(true);
  const [loadingPrefs, setLoadingPrefs] = useState(false);

  useEffect(() => {
    const fetchPrefs = async () => {
      try {
        setLoadingPrefs(true);
        const prefs = await api.getNotificationPreferences();
        setPrefTestRun(prefs.test_run_completed);
        setPrefDigest(prefs.knowledge_digest_ready);
        setPrefFreelance(prefs.freelance_task_assigned);
        setPrefMessage(prefs.new_message);
      } catch (err) {
        console.warn('Failed to load notification preferences', err);
      } finally {
        setLoadingPrefs(false);
      }
    };
    fetchPrefs();
  }, []);

  const handleSaveUrl = async () => {
    setSaving(true);
    try {
      await setApiUrl(urlInput);
      Alert.alert('Saved', 'API URL updated successfully');
    } catch {
      Alert.alert('Error', 'Failed to save API URL');
    } finally {
      setSaving(false);
    }
  };

  const handleTogglePref = async (key: string, value: boolean) => {
    if (key === 'test_run_completed') setPrefTestRun(value);
    else if (key === 'knowledge_digest_ready') setPrefDigest(value);
    else if (key === 'freelance_task_assigned') setPrefFreelance(value);
    else if (key === 'new_message') setPrefMessage(value);

    try {
      const payload = {
        test_run_completed: key === 'test_run_completed' ? value : prefTestRun,
        knowledge_digest_ready: key === 'knowledge_digest_ready' ? value : prefDigest,
        freelance_task_assigned: key === 'freelance_task_assigned' ? value : prefFreelance,
        new_message: key === 'new_message' ? value : prefMessage,
      };
      await api.updateNotificationPreferences(payload);
    } catch (err) {
      console.warn('Failed to save preference to backend', err);
    }
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Profile</Text>
        <View style={styles.profileCard}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>
              {user?.display_name?.charAt(0)?.toUpperCase() || 'U'}
            </Text>
          </View>
          <View style={styles.profileInfo}>
            <Text style={styles.profileName}>{user?.display_name || 'User'}</Text>
            <Text style={styles.profileEmail}>{user?.email || ''}</Text>
          </View>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Push Notifications</Text>
        {loadingPrefs ? (
          <ActivityIndicator size="small" color={colors.indigo[600]} style={{ marginVertical: spacing.md }} />
        ) : (
          <View style={styles.prefsList}>
            <View style={styles.prefRow}>
              <View style={styles.prefTextContainer}>
                <Text style={styles.prefLabel}>Test Run Completed</Text>
                <Text style={styles.prefDesc}>Receive push alerts when your SaaS test plans finish executing.</Text>
              </View>
              <Switch
                value={prefTestRun}
                onValueChange={(val) => handleTogglePref('test_run_completed', val)}
                trackColor={{ false: colors.slate[200], true: colors.indigo[500] }}
                thumbColor={colors.white}
              />
            </View>

            <View style={styles.prefRow}>
              <View style={styles.prefTextContainer}>
                <Text style={styles.prefLabel}>Knowledge Digest Ready</Text>
                <Text style={styles.prefDesc}>Be notified when the weekly aggregated AI summaries are synthesized.</Text>
              </View>
              <Switch
                value={prefDigest}
                onValueChange={(val) => handleTogglePref('knowledge_digest_ready', val)}
                trackColor={{ false: colors.slate[200], true: colors.indigo[500] }}
                thumbColor={colors.white}
              />
            </View>

            <View style={styles.prefRow}>
              <View style={styles.prefTextContainer}>
                <Text style={styles.prefLabel}>Freelance Task Assigned</Text>
                <Text style={styles.prefDesc}>Get alerts when a custom freelance job is analyzed and assigned.</Text>
              </View>
              <Switch
                value={prefFreelance}
                onValueChange={(val) => handleTogglePref('freelance_task_assigned', val)}
                trackColor={{ false: colors.slate[200], true: colors.indigo[500] }}
                thumbColor={colors.white}
              />
            </View>

            <View style={styles.prefRow}>
              <View style={styles.prefTextContainer}>
                <Text style={styles.prefLabel}>New Message</Text>
                <Text style={styles.prefDesc}>Real-time push alerts for AI assistant responses in your active chat.</Text>
              </View>
              <Switch
                value={prefMessage}
                onValueChange={(val) => handleTogglePref('new_message', val)}
                trackColor={{ false: colors.slate[200], true: colors.indigo[500] }}
                thumbColor={colors.white}
              />
            </View>
          </View>
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Connection</Text>
        <View style={styles.inputGroup}>
          <Text style={styles.label}>API URL</Text>
          <TextInput
            style={styles.input}
            value={urlInput}
            onChangeText={setUrlInput}
            placeholder="http://localhost:8000"
            placeholderTextColor={colors.slate[400]}
            autoCapitalize="none"
            autoCorrect={false}
          />
          <TouchableOpacity
            style={[styles.saveButton, saving && styles.saveButtonDisabled]}
            onPress={handleSaveUrl}
            disabled={saving}
          >
            <Text style={styles.saveButtonText}>
              {saving ? 'Saving...' : 'Save'}
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Appearance</Text>
        <View style={styles.themeRow}>
          {(['light', 'dark', 'system'] as const).map((t) => (
            <TouchableOpacity
              key={t}
              style={[styles.themeOption, theme === t && styles.themeOptionActive]}
              onPress={() => setTheme(t)}
            >
              <Text
                style={[
                  styles.themeOptionText,
                  theme === t && styles.themeOptionTextActive,
                ]}
              >
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      <View style={styles.section}>
        <TouchableOpacity style={styles.logoutButton} onPress={logout}>
          <Text style={styles.logoutButtonText}>Log Out</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.footer}>
        <Text style={styles.footerText}>Jarvis v1.0.0</Text>
        <Text style={styles.footerText}>Shipwright Engineering</Text>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.white,
  },
  section: {
    padding: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.slate[200],
  },
  sectionTitle: {
    fontSize: fontSize.xs,
    fontWeight: '600',
    color: colors.slate[500],
    textTransform: 'uppercase',
    marginBottom: spacing.lg,
  },
  profileCard: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.indigo[100],
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.md,
  },
  avatarText: {
    fontSize: fontSize.xl,
    fontWeight: '700',
    color: colors.indigo[700],
  },
  profileInfo: {
    flex: 1,
  },
  profileName: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.slate[900],
  },
  profileEmail: {
    fontSize: fontSize.sm,
    color: colors.slate[500],
  },
  inputGroup: {
    gap: spacing.sm,
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.slate[700],
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
  saveButton: {
    backgroundColor: colors.indigo[600],
    borderRadius: borderRadius.lg,
    paddingVertical: spacing.md,
    alignItems: 'center',
  },
  saveButtonDisabled: {
    opacity: 0.5,
  },
  saveButtonText: {
    color: colors.white,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
  themeRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  themeOption: {
    flex: 1,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.slate[200],
    alignItems: 'center',
  },
  themeOptionActive: {
    backgroundColor: colors.indigo[600],
    borderColor: colors.indigo[600],
  },
  themeOptionText: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.slate[600],
  },
  themeOptionTextActive: {
    color: colors.white,
  },
  logoutButton: {
    backgroundColor: colors.red[50],
    borderRadius: borderRadius.lg,
    paddingVertical: spacing.md,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.red[400],
  },
  logoutButtonText: {
    color: colors.red[500],
    fontSize: fontSize.md,
    fontWeight: '600',
  },
  footer: {
    padding: spacing['2xl'],
    alignItems: 'center',
  },
  footerText: {
    fontSize: fontSize.sm,
    color: colors.slate[400],
  },
  prefsList: {
    gap: spacing.lg,
  },
  prefRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  prefTextContainer: {
    flex: 1,
    paddingRight: spacing.md,
  },
  prefLabel: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.slate[800],
    marginBottom: 2,
  },
  prefDesc: {
    fontSize: fontSize.sm,
    color: colors.slate[500],
    lineHeight: 16,
  },
});

export default SettingsScreen;
