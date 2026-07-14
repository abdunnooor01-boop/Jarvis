import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  ScrollView,
} from 'react-native';
import api from '../services/api';
import { TestPlan, TestRun } from '../types/api';
import { colors, borderRadius, fontSize, spacing } from '../utils/theme';

const TestingScreen = () => {
  const [plans, setPlans] = useState<TestPlan[]>([]);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTab, setSelectedTab] = useState<'plans' | 'runs'>('plans');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [plansData, runsData] = await Promise.all([
        api.listTestPlans(),
        api.listTestRuns(),
      ]);
      setPlans(plansData);
      setRuns(runsData);
    } catch (err: any) {
      setError(err.detail || 'Failed to load testing data');
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
        <Text style={styles.title}>Testing Dashboard</Text>
      </View>

      <View style={styles.tabs}>
        <TouchableOpacity
          style={[styles.tab, selectedTab === 'plans' && styles.activeTab]}
          onPress={() => setSelectedTab('plans')}
        >
          <Text
            style={[styles.tabText, selectedTab === 'plans' && styles.activeTabText]}
          >
            Test Plans
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, selectedTab === 'runs' && styles.activeTab]}
          onPress={() => setSelectedTab('runs')}
        >
          <Text
            style={[styles.tabText, selectedTab === 'runs' && styles.activeTabText]}
          >
            Test Runs
          </Text>
        </TouchableOpacity>
      </View>

      {selectedTab === 'plans' ? (
        <FlatList
          data={plans}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Text style={styles.cardName}>{item.name}</Text>
                <View
                  style={[
                    styles.statusBadge,
                    item.status === 'active'
                      ? styles.statusActive
                      : styles.statusInactive,
                  ]}
                >
                  <Text style={styles.statusText}>{item.status}</Text>
                </View>
              </View>
              <Text style={styles.cardUrl}>{item.url}</Text>
              <View style={styles.statsRow}>
                <Text style={styles.stat}>
                  Passed: {item.passed}/{item.total_tests}
                </Text>
                <Text style={styles.stat}>Failed: {item.failed}</Text>
              </View>
            </View>
          )}
          ListEmptyComponent={
            <Text style={styles.emptyText}>No test plans</Text>
          }
        />
      ) : (
        <FlatList
          data={runs}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Text style={styles.cardName}>{item.name}</Text>
                <View
                  style={[
                    styles.statusBadge,
                    item.status === 'completed'
                      ? styles.statusCompleted
                      : item.status === 'running'
                      ? styles.statusRunning
                      : styles.statusFailed,
                  ]}
                >
                  <Text style={styles.statusText}>{item.status}</Text>
                </View>
              </View>
              <Text style={styles.cardUrl}>{item.url}</Text>
              <View style={styles.statsRow}>
                <Text style={styles.stat}>
                  Passed: {item.passed}/{item.total_tests}
                </Text>
                <Text style={styles.stat}>Failed: {item.failed}</Text>
              </View>
              {item.summary && (
                <Text style={styles.summary} numberOfLines={2}>
                  {item.summary}
                </Text>
              )}
            </View>
          )}
          ListEmptyComponent={
            <Text style={styles.emptyText}>No test runs</Text>
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
    marginBottom: spacing.sm,
  },
  cardName: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.slate[900],
    flex: 1,
  },
  statusBadge: {
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: 2,
  },
  statusActive: {
    backgroundColor: colors.green[500] + '20',
  },
  statusInactive: {
    backgroundColor: colors.slate[200],
  },
  statusCompleted: {
    backgroundColor: colors.green[500] + '20',
  },
  statusRunning: {
    backgroundColor: colors.indigo[100],
  },
  statusFailed: {
    backgroundColor: colors.red[50],
  },
  statusText: {
    fontSize: fontSize.xs,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  cardUrl: {
    fontSize: fontSize.sm,
    color: colors.slate[500],
    marginBottom: spacing.sm,
  },
  statsRow: {
    flexDirection: 'row',
    gap: spacing.lg,
  },
  stat: {
    fontSize: fontSize.sm,
    color: colors.slate[600],
  },
  summary: {
    fontSize: fontSize.sm,
    color: colors.slate[500],
    marginTop: spacing.sm,
    fontStyle: 'italic',
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

export default TestingScreen;