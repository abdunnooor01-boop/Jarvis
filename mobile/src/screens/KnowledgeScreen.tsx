import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import api from '../services/api';
import { DigestEntry, KnowledgeEntry } from '../types/api';
import { colors, borderRadius, fontSize, spacing } from '../utils/theme';

const KnowledgeScreen = () => {
  const [digest, setDigest] = useState<DigestEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [digestData, unreadData] = await Promise.all([
        api.getDigest(168),
        api.getUnreadCount(),
      ]);
      setDigest(digestData.entries);
      setUnread(unreadData.unread_count);
    } catch (err: any) {
      setError(err.detail || 'Failed to load knowledge');
    } finally {
      setLoading(false);
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
        <TouchableOpacity style={styles.retryButton} onPress={loadData}>
          <Text style={styles.retryButtonText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Knowledge Digest</Text>
        {unread > 0 && (
          <View style={styles.unreadBadge}>
            <Text style={styles.unreadText}>{unread} unread</Text>
          </View>
        )}
      </View>

      <FlatList
        data={digest}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => (
          <View style={styles.entryCard}>
            <View style={styles.entryHeader}>
              <Text style={styles.entryCategory}>{item.category}</Text>
              <Text style={styles.entryImportance}>{item.importance}</Text>
            </View>
            <Text style={styles.entryTitle}>{item.title}</Text>
            <Text style={styles.entrySummary} numberOfLines={3}>
              {item.summary}
            </Text>
            <Text style={styles.entryDate}>
              {new Date(item.created_at).toLocaleDateString()}
            </Text>
          </View>
        )}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>No knowledge entries yet</Text>
          </View>
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
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
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
  unreadBadge: {
    backgroundColor: colors.indigo[100],
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  unreadText: {
    fontSize: fontSize.xs,
    color: colors.indigo[700],
    fontWeight: '600',
  },
  list: {
    padding: spacing.lg,
  },
  entryCard: {
    backgroundColor: colors.slate[50],
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.slate[200],
  },
  entryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  entryCategory: {
    fontSize: fontSize.xs,
    color: colors.indigo[600],
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  entryImportance: {
    fontSize: fontSize.xs,
    color: colors.slate[500],
  },
  entryTitle: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.slate[900],
    marginBottom: spacing.xs,
  },
  entrySummary: {
    fontSize: fontSize.sm,
    color: colors.slate[600],
    lineHeight: 18,
    marginBottom: spacing.sm,
  },
  entryDate: {
    fontSize: fontSize.xs,
    color: colors.slate[400],
  },
  emptyContainer: {
    padding: spacing['3xl'],
    alignItems: 'center',
  },
  emptyText: {
    fontSize: fontSize.md,
    color: colors.slate[400],
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

export default KnowledgeScreen;