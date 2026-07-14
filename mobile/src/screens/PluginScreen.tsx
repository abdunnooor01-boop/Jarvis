import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Switch,
  TextInput,
  Alert,
} from 'react-native';
import api from '../services/api';
import { Plugin } from '../types/api';
import { colors, borderRadius, fontSize, spacing } from '../utils/theme';

const DISCOVER_PLUGINS: Plugin[] = [
  {
    id: 'discover-weather', name: 'Weather Forecaster', version: '1.0.0',
    description: 'Get live weather conditions and forecasts for any location.',
    author: 'Meteorology Group', enabled: false, settings: {}, tools: ['get_weather', 'forecast'],
  },
  {
    id: 'discover-spotify', name: 'Spotify Controller', version: '2.1.0',
    description: 'Control Spotify playback and search playlists natively.',
    author: 'MusicDevs', enabled: false, settings: {}, tools: ['play', 'pause', 'search'],
  },
  {
    id: 'discover-github', name: 'GitHub Agent', version: '1.4.2',
    description: 'Interact with GitHub repos, inspect commits, manage PRs.',
    author: 'GitCreators', enabled: false, settings: {}, tools: ['list_repos', 'view_commits'],
  },
  {
    id: 'discover-docker', name: 'Docker Manager', version: '1.2.0',
    description: 'Manage Docker containers, volumes, and networks.',
    author: 'SysOps Ltd', enabled: false, settings: {}, tools: ['ps', 'logs', 'inspect'],
  },
];

const PluginScreen = () => {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'installed' | 'browse'>('installed');
  const [searchQuery, setSearchQuery] = useState('');
  const [installing, setInstalling] = useState<string | null>(null);

  useEffect(() => { loadPlugins(); }, []);

  const loadPlugins = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listPlugins();
      setPlugins(data);
    } catch (err: any) {
      setError(err.detail || 'Failed to load plugins');
    } finally { setLoading(false); }
  };

  const togglePlugin = async (id: string, enabled: boolean) => {
    try {
      await api.togglePlugin(id, enabled);
      setPlugins((prev) => prev.map((p) => (p.id === id ? { ...p, enabled } : p)));
    } catch (err: any) {
      setError(err.detail || 'Failed to toggle plugin');
    }
  };

  const handleInstall = async (plugin: Plugin) => {
    setInstalling(plugin.id);
    try {
      const result = await api.installPlugin(`/plugins/${plugin.name.toLowerCase().replace(/\s+/g, '-')}`);
      Alert.alert('Installed', result.message);
      await loadPlugins();
    } catch (err: any) {
      Alert.alert('Error', err.detail || 'Failed to install plugin');
    } finally { setInstalling(null); }
  };

  if (loading) {
    return <View style={styles.center}><ActivityIndicator size="large" color={colors.indigo[600]} /></View>;
  }
  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.retryButton} onPress={loadPlugins}>
          <Text style={styles.retryButtonText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const filteredInstalled = plugins.filter(
    (p) => p.name.toLowerCase().includes(searchQuery.toLowerCase()) || p.description.toLowerCase().includes(searchQuery.toLowerCase())
  );
  const filteredDiscover = DISCOVER_PLUGINS.filter(
    (p) => p.name.toLowerCase().includes(searchQuery.toLowerCase()) || p.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Plugins</Text>
      </View>

      {/* Search */}
      <View style={styles.searchContainer}>
        <TextInput
          style={styles.searchInput}
          value={searchQuery}
          onChangeText={setSearchQuery}
          placeholder="Search plugins..."
          placeholderTextColor={colors.slate[400]}
        />
      </View>

      {/* Tabs */}
      <View style={styles.tabs}>
        <TouchableOpacity style={[styles.tab, activeTab === 'installed' && styles.activeTab]} onPress={() => setActiveTab('installed')}>
          <Text style={[styles.tabText, activeTab === 'installed' && styles.activeTabText]}>
            Installed ({plugins.length})
          </Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.tab, activeTab === 'browse' && styles.activeTab]} onPress={() => setActiveTab('browse')}>
          <Text style={[styles.tabText, activeTab === 'browse' && styles.activeTabText]}>
            Browse ({DISCOVER_PLUGINS.length})
          </Text>
        </TouchableOpacity>
      </View>

      {activeTab === 'installed' ? (
        <FlatList
          data={filteredInstalled}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <View style={styles.cardInfo}>
                  <Text style={styles.cardName}>{item.name}</Text>
                  <Text style={styles.cardVersion}>v{item.version}</Text>
                </View>
                <Switch
                  value={item.enabled}
                  onValueChange={(value) => togglePlugin(item.id, value)}
                  trackColor={{ false: colors.slate[300], true: colors.indigo[300] }}
                  thumbColor={item.enabled ? colors.indigo[600] : colors.slate[400]}
                />
              </View>
              <Text style={styles.cardDescription} numberOfLines={2}>{item.description}</Text>
              <Text style={styles.cardAuthor}>by {item.author}</Text>
              {item.tools && item.tools.length > 0 && (
                <View style={styles.toolsList}>
                  {item.tools.map((tool, i) => (
                    <View key={i} style={styles.toolBadge}>
                      <Text style={styles.toolBadgeText}>{tool}</Text>
                    </View>
                  ))}
                </View>
              )}
            </View>
          )}
          ListEmptyComponent={<Text style={styles.emptyText}>No plugins match your search</Text>}
        />
      ) : (
        <FlatList
          data={filteredDiscover}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <View style={styles.cardInfo}>
                  <Text style={styles.cardName}>{item.name}</Text>
                  <Text style={styles.cardVersion}>v{item.version}</Text>
                </View>
                <TouchableOpacity
                  style={[styles.installButton, installing === item.id && { opacity: 0.5 }]}
                  onPress={() => handleInstall(item)}
                  disabled={installing === item.id}
                >
                  <Text style={styles.installButtonText}>
                    {installing === item.id ? '...' : 'Install'}
                  </Text>
                </TouchableOpacity>
              </View>
              <Text style={styles.cardDescription} numberOfLines={2}>{item.description}</Text>
              <Text style={styles.cardAuthor}>by {item.author}</Text>
              {item.tools && item.tools.length > 0 && (
                <View style={styles.toolsList}>
                  {item.tools.map((tool, i) => (
                    <View key={i} style={styles.toolBadge}>
                      <Text style={styles.toolBadgeText}>{tool}</Text>
                    </View>
                  ))}
                </View>
              )}
            </View>
          )}
          ListEmptyComponent={<Text style={styles.emptyText}>No discoverable plugins match your search</Text>}
        />
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.white },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.white },
  header: { paddingHorizontal: spacing.lg, paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.slate[200] },
  title: { fontSize: fontSize.lg, fontWeight: '700', color: colors.slate[900] },
  searchContainer: { paddingHorizontal: spacing.lg, paddingVertical: spacing.sm },
  searchInput: { backgroundColor: colors.slate[50], borderWidth: 1, borderColor: colors.slate[200], borderRadius: borderRadius.lg, paddingHorizontal: spacing.lg, paddingVertical: spacing.md, fontSize: fontSize.md, color: colors.slate[900] },
  tabs: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: colors.slate[200] },
  tab: { flex: 1, paddingVertical: spacing.md, alignItems: 'center', borderBottomWidth: 2, borderBottomColor: 'transparent' },
  activeTab: { borderBottomColor: colors.indigo[600] },
  tabText: { fontSize: fontSize.md, fontWeight: '500', color: colors.slate[500] },
  activeTabText: { color: colors.indigo[600], fontWeight: '600' },
  list: { padding: spacing.lg },
  card: { backgroundColor: colors.slate[50], borderRadius: borderRadius.lg, padding: spacing.lg, marginBottom: spacing.md, borderWidth: 1, borderColor: colors.slate[200] },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.sm },
  cardInfo: { flex: 1 },
  cardName: { fontSize: fontSize.md, fontWeight: '600', color: colors.slate[900] },
  cardVersion: { fontSize: fontSize.xs, color: colors.slate[400] },
  cardDescription: { fontSize: fontSize.sm, color: colors.slate[600], lineHeight: 18, marginBottom: spacing.xs },
  cardAuthor: { fontSize: fontSize.xs, color: colors.slate[400] },
  toolsList: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginTop: spacing.sm },
  toolBadge: { backgroundColor: colors.indigo[50], borderRadius: borderRadius.full, paddingHorizontal: spacing.sm, paddingVertical: 2, borderWidth: 1, borderColor: colors.indigo[200] },
  toolBadgeText: { fontSize: 9, color: colors.indigo[700], fontWeight: '500' },
  installButton: { backgroundColor: colors.indigo[600], borderRadius: borderRadius.md, paddingHorizontal: spacing.lg, paddingVertical: spacing.sm },
  installButtonText: { color: colors.white, fontSize: fontSize.sm, fontWeight: '600' },
  emptyText: { textAlign: 'center', color: colors.slate[400], padding: spacing['3xl'], fontSize: fontSize.md },
  errorText: { fontSize: fontSize.md, color: colors.red[500], marginBottom: spacing.lg },
  retryButton: { backgroundColor: colors.indigo[600], borderRadius: borderRadius.lg, paddingHorizontal: spacing['2xl'], paddingVertical: spacing.md },
  retryButtonText: { color: colors.white, fontSize: fontSize.md, fontWeight: '600' },
});

export default PluginScreen;