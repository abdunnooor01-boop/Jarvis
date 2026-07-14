import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
  TextInput,
} from 'react-native';
import { useOfflineQueueStore, QueuedTask, TaskStatus } from '../stores/offlineQueue';
import { colors, borderRadius, fontSize, spacing } from '../utils/theme';

const TASK_TEMPLATES = [
  { endpoint: '/tasks/queue', method: 'POST' as const, body: { type: 'run_tests' }, description: 'Run automated tests' },
  { endpoint: '/tasks/queue', method: 'POST' as const, body: { type: 'scrape_url' }, description: 'Scrape a URL' },
  { endpoint: '/tasks/queue', method: 'POST' as const, body: { type: 'research' }, description: 'Web research task' },
  { endpoint: '/tasks/queue', method: 'POST' as const, body: { type: 'data_entry' }, description: 'Data entry task' },
];

const TaskQueueScreen = () => {
  const {
    offlineQueue,
    serverTasks,
    isOnline,
    isSyncing,
    queueTask,
    syncQueue,
    fetchServerTasks,
    removeFromQueue,
  } = useOfflineQueueStore();
  const [selectedTab, setSelectedTab] = useState<'queued' | 'history'>('queued');
  const [customDescription, setCustomDescription] = useState('');

  useEffect(() => {
    fetchServerTasks();
  }, []);

  const handleQueueTask = async (template: typeof TASK_TEMPLATES[0]) => {
    const description = customDescription.trim() || template.description;
    await queueTask({
      endpoint: template.endpoint,
      method: template.method,
      body: { ...template.body, description },
      description,
    });
    setCustomDescription('');

    if (!isOnline) {
      Alert.alert(
        'Task Queued Offline',
        'Your task has been saved locally. It will be submitted automatically when you reconnect.',
      );
    } else {
      Alert.alert('Task Submitted', `Task "${description}" has been queued.`);
    }
  };

  const renderQueuedItem = ({ item }: { item: QueuedTask }) => (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Text style={styles.cardDescription}>{item.description}</Text>
        <TouchableOpacity
          onPress={() => {
            removeFromQueue(item.id);
          }}
        >
          <Text style={styles.removeText}>Remove</Text>
        </TouchableOpacity>
      </View>
      <Text style={styles.cardMeta}>
        Queued: {new Date(item.queuedAt).toLocaleTimeString()}
      </Text>
    </View>
  );

  const renderTaskItem = ({ item }: { item: TaskStatus }) => (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Text style={styles.cardDescription}>{item.description}</Text>
        <View
          style={[
            styles.statusBadge,
            item.status === 'completed' && styles.statusCompleted,
            item.status === 'in_progress' && styles.statusRunning,
            item.status === 'failed' && styles.statusFailed,
            item.status === 'queued' && styles.statusQueued,
          ]}
        >
          <Text style={styles.statusText}>{item.status.replace('_', ' ')}</Text>
        </View>
      </View>
      <Text style={styles.cardMeta}>Type: {item.type}</Text>
      {item.result && (
        <Text style={styles.cardResult} numberOfLines={3}>
          Result: {JSON.stringify(item.result)}
        </Text>
      )}
      {item.error && <Text style={styles.cardError}>Error: {item.error}</Text>}
      {item.completedAt && (
        <Text style={styles.cardMeta}>
          Completed: {new Date(item.completedAt).toLocaleString()}
        </Text>
      )}
    </View>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Task Queue</Text>
        <View style={styles.statusRow}>
          <View
            style={[
              styles.connectionDot,
              isOnline ? styles.online : styles.offline,
            ]}
          />
          <Text style={styles.statusText}>
            {isOnline ? 'Online' : 'Offline'}
          </Text>
        </View>
      </View>

      {/* Queue new task */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Queue a Task</Text>
        <TextInput
          style={styles.input}
          value={customDescription}
          onChangeText={setCustomDescription}
          placeholder="Describe your task (optional)"
          placeholderTextColor={colors.slate[400]}
        />
        <View style={styles.templateRow}>
          {TASK_TEMPLATES.map((template, index) => (
            <TouchableOpacity
              key={index}
              style={styles.templateButton}
              onPress={() => handleQueueTask(template)}
            >
              <Text style={styles.templateButtonText}>{template.description}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Tabs */}
      <View style={styles.tabs}>
        <TouchableOpacity
          style={[styles.tab, selectedTab === 'queued' && styles.activeTab]}
          onPress={() => setSelectedTab('queued')}
        >
          <Text
            style={[styles.tabText, selectedTab === 'queued' && styles.activeTabText]}
          >
            Queued ({offlineQueue.length})
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, selectedTab === 'history' && styles.activeTab]}
          onPress={() => setSelectedTab('history')}
        >
          <Text
            style={[styles.tabText, selectedTab === 'history' && styles.activeTabText]}
          >
            History
          </Text>
        </TouchableOpacity>
      </View>

      {selectedTab === 'queued' ? (
        <FlatList
          data={offlineQueue}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          renderItem={renderQueuedItem}
          ListEmptyComponent={
            <Text style={styles.emptyText}>No tasks in queue</Text>
          }
          ListFooterComponent={
            offlineQueue.length > 0 ? (
              <TouchableOpacity
                style={[styles.syncButton, isSyncing && styles.syncButtonDisabled]}
                onPress={syncQueue}
                disabled={isSyncing}
              >
                {isSyncing ? (
                  <ActivityIndicator size="small" color={colors.white} />
                ) : (
                  <Text style={styles.syncButtonText}>
                    {isOnline ? 'Submit Now' : 'Waiting for connection...'}
                  </Text>
                )}
              </TouchableOpacity>
            ) : null
          }
        />
      ) : (
        <FlatList
          data={serverTasks}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          renderItem={renderTaskItem}
          ListEmptyComponent={
            <Text style={styles.emptyText}>No task history</Text>
          }
          ListFooterComponent={
            <TouchableOpacity style={styles.refreshButton} onPress={fetchServerTasks}>
              <Text style={styles.refreshButtonText}>Refresh</Text>
            </TouchableOpacity>
          }
        />
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.white },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.slate[200],
  },
  title: { fontSize: fontSize.lg, fontWeight: '700', color: colors.slate[900] },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  connectionDot: { width: 8, height: 8, borderRadius: 4 },
  online: { backgroundColor: colors.green[500] },
  offline: { backgroundColor: colors.red[500] },
  section: { padding: spacing.lg, borderBottomWidth: 1, borderBottomColor: colors.slate[200] },
  sectionTitle: { fontSize: fontSize.sm, fontWeight: '600', color: colors.slate[700], marginBottom: spacing.sm },
  input: {
    backgroundColor: colors.slate[50],
    borderWidth: 1,
    borderColor: colors.slate[200],
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    fontSize: fontSize.md,
    color: colors.slate[900],
    marginBottom: spacing.md,
  },
  templateRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  templateButton: {
    backgroundColor: colors.indigo[50],
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderWidth: 1,
    borderColor: colors.indigo[200],
  },
  templateButtonText: { fontSize: fontSize.sm, color: colors.indigo[700], fontWeight: '500' },
  tabs: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: colors.slate[200] },
  tab: { flex: 1, paddingVertical: spacing.md, alignItems: 'center', borderBottomWidth: 2, borderBottomColor: 'transparent' },
  activeTab: { borderBottomColor: colors.indigo[600] },
  tabText: { fontSize: fontSize.md, fontWeight: '500', color: colors.slate[500] },
  activeTabText: { color: colors.indigo[600], fontWeight: '600' },
  list: { padding: spacing.lg },
  card: {
    backgroundColor: colors.slate[50],
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.slate[200],
  },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: spacing.xs },
  cardDescription: { fontSize: fontSize.md, fontWeight: '600', color: colors.slate[900], flex: 1 },
  cardMeta: { fontSize: fontSize.xs, color: colors.slate[400], marginTop: spacing.xs },
  cardResult: { fontSize: fontSize.sm, color: colors.slate[600], marginTop: spacing.sm, fontStyle: 'italic' },
  cardError: { fontSize: fontSize.sm, color: colors.red[500], marginTop: spacing.sm },
  removeText: { fontSize: fontSize.sm, color: colors.red[500], marginLeft: spacing.sm },
  statusBadge: { borderRadius: borderRadius.full, paddingHorizontal: spacing.md, paddingVertical: 2, marginLeft: spacing.sm },
  statusCompleted: { backgroundColor: colors.green[500] + '20' },
  statusRunning: { backgroundColor: colors.indigo[100] },
  statusFailed: { backgroundColor: colors.red[50] },
  statusQueued: { backgroundColor: colors.slate[200] },
  statusText: { fontSize: fontSize.xs, fontWeight: '600', textTransform: 'capitalize' },
  emptyText: { textAlign: 'center', color: colors.slate[400], padding: spacing['3xl'], fontSize: fontSize.md },
  syncButton: {
    backgroundColor: colors.indigo[600],
    borderRadius: borderRadius.lg,
    paddingVertical: spacing.md,
    alignItems: 'center',
    marginTop: spacing.md,
  },
  syncButtonDisabled: { opacity: 0.5 },
  syncButtonText: { color: colors.white, fontSize: fontSize.md, fontWeight: '600' },
  refreshButton: {
    backgroundColor: colors.slate[200],
    borderRadius: borderRadius.lg,
    paddingVertical: spacing.md,
    alignItems: 'center',
    marginTop: spacing.md,
  },
  refreshButtonText: { color: colors.slate[700], fontSize: fontSize.md, fontWeight: '600' },
});

export default TaskQueueScreen;