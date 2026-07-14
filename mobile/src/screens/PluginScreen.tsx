import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Switch,
} from 'react-native';
import api from '../services/api';
import { Plugin } from '../types/api';
import { colors, borderRadius, fontSize, spacing } from '../utils/theme';

const PluginScreen = () => {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadPlugins();
  }, []);

  const loadPlugins = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listPlugins();
      setPlugins(data);
    } catch (err: any) {
      setError(err.detail || 'Failed to load plugins');
    } finally {
      setLoading(false);
    }
  };

  const togglePlugin = async (id: string, enabled: boolean) => {
    try {
      await api.togglePlugin(id, enabled);
      setPlugins((prev) =>
        prev.map((p) => (p.id === id ? { ...p, enabled } : p)),
      );
    } catch (err: any) {
      setError(err.detail || 'Failed to toggle plugin');
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={colors.indigo[600]} />
      </View>
    );
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

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Plugins</Text>
      </View>

      <FlatList
        data={plugins}
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
                trackColor={{
                  false: colors.slate[300],
                  true: colors.indigo[300],
                }}
                thumbColor={item.enabled ? colors.indigo[600] : colors.slate[400]}
              />
            </View>
            <Text style={styles.cardDescription} numberOfLines={2}>
              {item.description}
            </Text>
            <Text style={styles.cardAuthor}>by {item.author}</Text>
          </View>
        )}
        ListEmptyComponent={
          <Text style={styles.emptyText}>No plugins installed</Text>
        }
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.white,
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.white,
  },
  header: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.slate[200],
  },
  title: {
    fontSize: fontSize.lg,
    fontWeight: '700',
    color: colors.slate[900],
  },
  list: {
    padding: spacing.lg,
  },
  card: {
    backgroundColor: colors.slate[50],
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.slate[200],
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  cardInfo: {
    flex: 1,
  },
  cardName: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.slate[900],
  },
  cardVersion: {
    fontSize: fontSize.xs,
    color: colors.slate[400],
  },
  cardDescription: {
    fontSize: fontSize.sm,
    color: colors.slate[600],
    lineHeight: 18,
    marginBottom: spacing.xs,
  },
  cardAuthor: {
    fontSize: fontSize.xs,
    color: colors.slate[400],
  },
  emptyText: {
    textAlign: 'center',
    color: colors.slate[400],
    padding: spacing['3xl'],
    fontSize: fontSize.md,
  },
  errorText: {
    fontSize: fontSize.md,
    color: colors.red[500],
    marginBottom: spacing.lg,
  },
  retryButton: {
    backgroundColor: colors.indigo[600],
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing['2xl'],
    paddingVertical: spacing.md,
  },
  retryButtonText: {
    color: colors.white,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
});

export default PluginScreen;