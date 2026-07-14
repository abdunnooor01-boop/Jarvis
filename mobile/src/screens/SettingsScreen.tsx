import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Switch,
  Alert,
} from 'react-native';
import { useAuthStore } from '../stores/auth';
import { useSettingsStore } from '../stores/settings';
import { colors, borderRadius, fontSize, spacing } from '../utils/theme';

const SettingsScreen = () => {
  const { user, logout } = useAuthStore();
  const { apiUrl, theme, fontSize: appFontSize, setApiUrl, setTheme } = useSettingsStore();
  const [urlInput, setUrlInput] = useState(apiUrl);
  const [saving, setSaving] = useState(false);
  const [pushEnabled, setPushEnabled] = useState(true);
  const [emailEnabled, setEmailEnabled] = useState(false);

  const handleSaveUrl = async () => {
    setSaving(true);
    try {
      await setApiUrl(urlInput);
      Alert.alert('Saved', 'API URL updated');
    } catch {
      Alert.alert('Error', 'Failed to save');
    } finally { setSaving(false); }
  };

  return (
    <ScrollView style={styles.container}>
      {/* Profile Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Profile</Text>
        <View style={styles.profileCard}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{user?.display_name?.charAt(0)?.toUpperCase() || 'U'}</Text>
          </View>
          <View style={styles.profileInfo}>
            <Text style={styles.profileName}>{user?.display_name || 'User'}</Text>
            <Text style={styles.profileEmail}>{user?.email || ''}</Text>
          </View>
        </View>
      </View>

      {/* Connection Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Connection</Text>
        <View style={styles.inputGroup}>
          <Text style={styles.label}>API URL</Text>
          <TextInput style={styles.input} value={urlInput} onChangeText={setUrlInput}
            placeholder="http://localhost:8000" placeholderTextColor={colors.slate[400]}
            autoCapitalize="none" autoCorrect={false} />
          <TouchableOpacity style={[styles.saveButton, saving && { opacity: 0.5 }]} onPress={handleSaveUrl} disabled={saving}>
            <Text style={styles.saveButtonText}>{saving ? 'Saving...' : 'Save'}</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Notifications Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Notifications</Text>
        <View style={styles.switchRow}>
          <View style={styles.switchLabel}>
            <Text style={styles.switchTitle}>Push Notifications</Text>
            <Text style={styles.switchDesc}>Receive alerts on your device</Text>
          </View>
          <Switch value={pushEnabled} onValueChange={setPushEnabled}
            trackColor={{ false: colors.slate[300], true: colors.indigo[300] }}
            thumbColor={pushEnabled ? colors.indigo[600] : colors.slate[400]} />
        </View>
        <View style={styles.switchRow}>
          <View style={styles.switchLabel}>
            <Text style={styles.switchTitle}>Email Notifications</Text>
            <Text style={styles.switchDesc}>Receive email updates</Text>
          </View>
          <Switch value={emailEnabled} onValueChange={setEmailEnabled}
            trackColor={{ false: colors.slate[300], true: colors.indigo[300] }}
            thumbColor={emailEnabled ? colors.indigo[600] : colors.slate[400]} />
        </View>
      </View>

      {/* Appearance Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Appearance</Text>
        <View style={styles.themeRow}>
          {(['light', 'dark', 'system'] as const).map((t) => (
            <TouchableOpacity key={t} style={[styles.themeOption, theme === t && styles.themeOptionActive]} onPress={() => setTheme(t)}>
              <Text style={[styles.themeOptionText, theme === t && styles.themeOptionTextActive]}>
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Language Section (placeholder — populated by multilingual support) */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Language</Text>
        <Text style={styles.languageNote}>Auto-detect (system default)</Text>
      </View>

      {/* About Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>About</Text>
        <View style={styles.aboutRow}>
          <Text style={styles.aboutLabel}>Version</Text>
          <Text style={styles.aboutValue}>1.0.0</Text>
        </View>
        <View style={styles.aboutRow}>
          <Text style={styles.aboutLabel}>Build</Text>
          <Text style={styles.aboutValue}>2026.07.13</Text>
        </View>
        <View style={styles.aboutRow}>
          <Text style={styles.aboutLabel}>Framework</Text>
          <Text style={styles.aboutValue}>React Native (Expo)</Text>
        </View>
        <View style={styles.aboutRow}>
          <Text style={styles.aboutLabel}>Team</Text>
          <Text style={styles.aboutValue}>Shipwright Engineering</Text>
        </View>
      </View>

      {/* Logout */}
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
  container: { flex: 1, backgroundColor: colors.white },
  section: { padding: spacing.lg, borderBottomWidth: 1, borderBottomColor: colors.slate[200] },
  sectionTitle: { fontSize: fontSize.xs, fontWeight: '600', color: colors.slate[500], textTransform: 'uppercase', marginBottom: spacing.lg },
  profileCard: { flexDirection: 'row', alignItems: 'center' },
  avatar: { width: 48, height: 48, borderRadius: 24, backgroundColor: colors.indigo[100], justifyContent: 'center', alignItems: 'center', marginRight: spacing.md },
  avatarText: { fontSize: fontSize.xl, fontWeight: '700', color: colors.indigo[700] },
  profileInfo: { flex: 1 },
  profileName: { fontSize: fontSize.lg, fontWeight: '600', color: colors.slate[900] },
  profileEmail: { fontSize: fontSize.sm, color: colors.slate[500] },
  inputGroup: { gap: spacing.sm },
  label: { fontSize: fontSize.sm, fontWeight: '600', color: colors.slate[700] },
  input: { backgroundColor: colors.slate[50], borderWidth: 1, borderColor: colors.slate[200], borderRadius: borderRadius.lg, paddingHorizontal: spacing.lg, paddingVertical: spacing.md, fontSize: fontSize.md, color: colors.slate[900] },
  saveButton: { backgroundColor: colors.indigo[600], borderRadius: borderRadius.lg, paddingVertical: spacing.md, alignItems: 'center' },
  saveButtonText: { color: colors.white, fontSize: fontSize.md, fontWeight: '600' },
  switchRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.slate[100] },
  switchLabel: { flex: 1, marginRight: spacing.md },
  switchTitle: { fontSize: fontSize.md, fontWeight: '500', color: colors.slate[900] },
  switchDesc: { fontSize: fontSize.sm, color: colors.slate[500], marginTop: 2 },
  themeRow: { flexDirection: 'row', gap: spacing.sm },
  themeOption: { flex: 1, paddingVertical: spacing.md, borderRadius: borderRadius.lg, borderWidth: 1, borderColor: colors.slate[200], alignItems: 'center' },
  themeOptionActive: { backgroundColor: colors.indigo[600], borderColor: colors.indigo[600] },
  themeOptionText: { fontSize: fontSize.sm, fontWeight: '600', color: colors.slate[600] },
  themeOptionTextActive: { color: colors.white },
  languageNote: { fontSize: fontSize.md, color: colors.slate[600] },
  aboutRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.slate[100] },
  aboutLabel: { fontSize: fontSize.md, color: colors.slate[700] },
  aboutValue: { fontSize: fontSize.md, color: colors.slate[900], fontWeight: '500' },
  logoutButton: { backgroundColor: colors.red[50], borderRadius: borderRadius.lg, paddingVertical: spacing.md, alignItems: 'center', borderWidth: 1, borderColor: colors.red[400] },
  logoutButtonText: { color: colors.red[500], fontSize: fontSize.md, fontWeight: '600' },
  footer: { padding: spacing['2xl'], alignItems: 'center' },
  footerText: { fontSize: fontSize.sm, color: colors.slate[400] },
});

export default SettingsScreen;