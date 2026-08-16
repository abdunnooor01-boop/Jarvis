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
import { TaskTemplate, FreelanceJob } from '../types/api';
import { colors, borderRadius, fontSize, spacing } from '../utils/theme';

const FreelanceScreen = () => {
  const [templates, setTemplates] = useState<TaskTemplate[]>([]);
  const [jobs, setJobs] = useState<FreelanceJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTab, setSelectedTab] = useState<'templates' | 'jobs'>('templates');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [templatesData, jobsData] = await Promise.all([
        api.listTaskTemplates(),
        api.listJobs(),
      ]);
      setTemplates(templatesData);
      setJobs(jobsData);
    } catch (err: any) {
      setError(err.detail || 'Failed to load freelance data');
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

  const formatPrice = (cents: number) => `$${(cents / 100).toFixed(2)}`;

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Freelance Tasks</Text>
      </View>

      <View style={styles.tabs}>
        <TouchableOpacity
          style={[styles.tab, selectedTab === 'templates' && styles.activeTab]}
          onPress={() => setSelectedTab('templates')}
        >
          <Text
            style={[styles.tabText, selectedTab === 'templates' && styles.activeTabText]}
          >
            Available Tasks
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, selectedTab === 'jobs' && styles.activeTab]}
          onPress={() => setSelectedTab('jobs')}
        >
          <Text
            style={[styles.tabText, selectedTab === 'jobs' && styles.activeTabText]}
          >
            My Jobs
          </Text>
        </TouchableOpacity>
      </View>

      {selectedTab === 'templates' ? (
        <FlatList
          data={templates}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Text style={styles.cardName}>{item.name}</Text>
                <Text style={styles.cardPrice}>{formatPrice(item.price_cents)}</Text>
              </View>
              <Text style={styles.cardCategory}>{item.category}</Text>
              <Text style={styles.cardDescription} numberOfLines={2}>
                {item.description}
              </Text>
              <Text style={styles.cardDuration}>
                Est. {item.estimated_minutes} minutes
              </Text>
            </View>
          )}
          ListEmptyComponent={
            <Text style={styles.emptyText}>No tasks available</Text>
          }
        />
      ) : (
        <FlatList
          data={jobs}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Text style={styles.cardName}>{item.template_name}</Text>
                <View
                  style={[
                    styles.statusBadge,
                    item.status === 'completed'
                      ? styles.statusCompleted
                      : item.status === 'in_progress'
                      ? styles.statusRunning
                      : styles.statusPending,
                  ]}
                >
                  <Text style={styles.statusText}>{item.status}</Text>
                </View>
              </View>
              <Text style={styles.cardPrice}>{formatPrice(item.price_cents)}</Text>
              <Text style={styles.cardDate}>
                {new Date(item.created_at).toLocaleDateString()}
              </Text>
            </View>
          )}
          ListEmptyComponent={
            <Text style={styles.emptyText}>No jobs yet</Text>
          }
        />
      )}
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
  tabs: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: colors.slate[200],
  },
  tab: {
    flex: 1,
    paddingVertical: spacing.md,
    alignItems: 'center',
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  activeTab: {
    borderBottomColor: colors.indigo[600],
  },
  tabText: {
    fontSize: fontSize.md,
    fontWeight: '500',
    color: colors.slate[500],
  },
  activeTabText: {
    color: colors.indigo[600],
    fontWeight: '600',
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
    marginBottom: spacing.xs,
  },
  cardName: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.slate[900],
    flex: 1,
  },
  cardPrice: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.indigo[600],
  },
  cardCategory: {
    fontSize: fontSize.xs,
    color: colors.indigo[600],
    fontWeight: '600',
    textTransform: 'uppercase',
    marginBottom: spacing.xs,
  },
  cardDescription: {
    fontSize: fontSize.sm,
    color: colors.slate[600],
    lineHeight: 18,
    marginBottom: spacing.sm,
  },
  cardDuration: {
    fontSize: fontSize.xs,
    color: colors.slate[400],
  },
  cardDate: {
    fontSize: fontSize.xs,
    color: colors.slate[400],
    marginTop: spacing.xs,
  },
  statusBadge: {
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: 2,
  },
  statusCompleted: {
    backgroundColor: colors.green[500] + '20',
  },
  statusRunning: {
    backgroundColor: colors.indigo[100],
  },
  statusPending: {
    backgroundColor: colors.slate[200],
  },
  statusText: {
    fontSize: fontSize.xs,
    fontWeight: '600',
    textTransform: 'capitalize',
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

export default FreelanceScreen;