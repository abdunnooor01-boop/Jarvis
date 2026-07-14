import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  TextInput,
  ScrollView,
  Alert,
} from 'react-native';
import api from '../services/api';
import { DigestEntry, KnowledgeEntry, KnowledgeSource } from '../types/api';
import { colors, borderRadius, fontSize, spacing } from '../utils/theme';

type TabType = 'digest' | 'entries' | 'sources' | 'addSource';

const KnowledgeScreen = () => {
  const [activeTab, setActiveTab] = useState<TabType>('digest');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Data states
  const [digest, setDigest] = useState<DigestEntry[]>([]);
  const [unread, setUnread] = useState(0);
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);

  // Search & Filter states (for entries)
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');

  // Detail view state
  const [selectedEntry, setSelectedEntry] = useState<KnowledgeEntry | null>(null);

  // Form states
  const [formName, setFormName] = useState('');
  const [formUrl, setFormUrl] = useState('');
  const [formCategory, setFormCategory] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeTab === 'digest') {
        const [digestData, unreadData] = await Promise.all([
          api.getDigest(168),
          api.getUnreadCount(),
        ]);
        setDigest(digestData.entries || []);
        setUnread(unreadData.unread_count);
      } else if (activeTab === 'entries') {
        const entriesData = await api.listKnowledgeEntries();
        // Backend could return list or paginated object, normalize it
        const normalizedEntries = Array.isArray(entriesData) 
          ? entriesData 
          : (entriesData as any).items || [];
        setEntries(normalizedEntries);
      } else if (activeTab === 'sources') {
        const sourcesData = await api.getKnowledgeSources();
        const normalizedSources = Array.isArray(sourcesData)
          ? sourcesData
          : (sourcesData as any).items || [];
        setSources(normalizedSources);
      }
    } catch (err: any) {
      setError(err.detail || err.message || 'Failed to load knowledge data');
    } finally {
      setLoading(false);
    }
  };

  const handleAddSource = async () => {
    if (!formName || !formUrl || !formCategory) {
      Alert.alert('Error', 'Please fill in all fields');
      return;
    }
    setSubmitting(true);
    try {
      await api.addKnowledgeSource({
        name: formName,
        url: formUrl,
        category: formCategory,
      });
      Alert.alert('Success', 'Knowledge source added successfully!');
      setFormName('');
      setFormUrl('');
      setFormCategory('');
      setActiveTab('sources');
    } catch (err: any) {
      Alert.alert('Error', err.detail || err.message || 'Failed to add source');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRefreshSource = async (id: string) => {
    try {
      Alert.alert('Syncing', 'Crawl and fetch initiated...');
      await api.refreshKnowledgeSource(id);
      Alert.alert('Success', 'Source sync complete!');
      if (activeTab === 'sources') loadData();
    } catch (err: any) {
      Alert.alert('Error', err.detail || err.message || 'Failed to refresh source');
    }
  };

  const handleMarkAsRead = async (id: string) => {
    try {
      await api.markKnowledgeEntryRead(id);
      if (selectedEntry && selectedEntry.id === id) {
        setSelectedEntry({ ...selectedEntry, read: true });
      }
      setEntries(entries.map(e => e.id === id ? { ...e, read: true } : e));
    } catch (err: any) {
      console.warn('Failed to mark as read', err);
    }
  };

  // Extract unique categories from entries
  const categories = ['All', ...Array.from(new Set(entries.map(e => e.category).filter(Boolean)))];

  const filteredEntries = entries.filter(e => {
    const matchesSearch = e.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          (e.summary && e.summary.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesCategory = selectedCategory === 'All' || e.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  if (selectedEntry) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => setSelectedEntry(null)} style={styles.backButton}>
            <Text style={styles.backButtonText}>← Back</Text>
          </TouchableOpacity>
          <Text style={styles.title} numberOfLines={1}>Entry Detail</Text>
          <View style={{ width: 60 }} />
        </View>

        <ScrollView contentContainerStyle={styles.detailScroll}>
          <Text style={styles.detailCategory}>{selectedEntry.category || 'GENERAL'}</Text>
          <Text style={styles.detailTitle}>{selectedEntry.title}</Text>
          <Text style={styles.detailSource}>Source: {selectedEntry.source} • {new Date(selectedEntry.created_at).toLocaleDateString()}</Text>

          <View style={styles.sectionContainer}>
            <Text style={styles.sectionTitle}>AI Summary</Text>
            <Text style={styles.summaryText}>{selectedEntry.summary}</Text>
          </View>

          {selectedEntry.content ? (
            <View style={styles.sectionContainer}>
              <Text style={styles.sectionTitle}>Full Content</Text>
              <Text style={styles.contentText}>{selectedEntry.content}</Text>
            </View>
          ) : null}

          {selectedEntry.url ? (
            <Text style={styles.detailUrl} numberOfLines={1}>Original URL: {selectedEntry.url}</Text>
          ) : null}

          {!selectedEntry.read && (
            <TouchableOpacity 
              style={styles.markReadButton} 
              onPress={() => handleMarkAsRead(selectedEntry.id)}
            >
              <Text style={styles.markReadButtonText}>Mark as Read</Text>
            </TouchableOpacity>
          )}
        </ScrollView>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Knowledge Base</Text>
        {activeTab === 'digest' && unread > 0 && (
          <View style={styles.unreadBadge}>
            <Text style={styles.unreadText}>{unread} unread</Text>
          </View>
        )}
      </View>

      {/* Tabs */}
      <View style={styles.tabsContainer}>
        {(['digest', 'entries', 'sources', 'addSource'] as TabType[]).map((tab) => (
          <TouchableOpacity
            key={tab}
            style={[styles.tabButton, activeTab === tab && styles.activeTabButton]}
            onPress={() => setActiveTab(tab)}
          >
            <Text style={[styles.tabButtonText, activeTab === tab && styles.activeTabButtonText]}>
              {tab === 'addSource' ? '+ Source' : tab.charAt(0).toUpperCase() + tab.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.indigo[600]} />
        </View>
      ) : error ? (
        <View style={styles.center}>
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity style={styles.retryButton} onPress={loadData}>
            <Text style={styles.retryButtonText}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : activeTab === 'digest' ? (
        <FlatList
          data={digest}
          keyExtractor={(item, index) => item.id || index.toString()}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <View style={styles.entryCard}>
              <View style={styles.entryHeader}>
                <Text style={styles.entryCategory}>{item.category || 'Digest'}</Text>
                <View style={[styles.importanceBadge, item.importance === 'high' && styles.importanceHigh]}>
                  <Text style={[styles.importanceText, item.importance === 'high' && styles.importanceHighText]}>
                    {item.importance || 'normal'}
                  </Text>
                </View>
              </View>
              <Text style={styles.entryTitle}>{item.title}</Text>
              <Text style={styles.entrySummary}>{item.summary}</Text>
              <Text style={styles.entryDate}>
                {new Date(item.created_at).toLocaleDateString()}
              </Text>
            </View>
          )}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>No digest entries for this week</Text>
            </View>
          }
        />
      ) : activeTab === 'entries' ? (
        <View style={{ flex: 1 }}>
          {/* Search bar & Categories scroll */}
          <View style={styles.searchBarContainer}>
            <TextInput
              style={styles.searchInput}
              placeholder="Search entries..."
              placeholderTextColor={colors.slate[400]}
              value={searchQuery}
              onChangeText={setSearchQuery}
            />
          </View>
          <View style={styles.categoriesContainer}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              {categories.map((cat) => (
                <TouchableOpacity
                  key={cat}
                  style={[styles.categoryChip, selectedCategory === cat && styles.activeCategoryChip]}
                  onPress={() => setSelectedCategory(cat)}
                >
                  <Text style={[styles.categoryChipText, selectedCategory === cat && styles.activeCategoryChipText]}>
                    {cat}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>

          <FlatList
            data={filteredEntries}
            keyExtractor={(item) => item.id}
            contentContainerStyle={styles.list}
            renderItem={({ item }) => (
              <TouchableOpacity style={styles.entryCard} onPress={() => setSelectedEntry(item)}>
                <View style={styles.entryHeader}>
                  <Text style={styles.entryCategory}>{item.category || 'General'}</Text>
                  <Text style={styles.entrySource}>{item.source}</Text>
                </View>
                <Text style={[styles.entryTitle, item.read && styles.readTitle]}>{item.title}</Text>
                <Text style={styles.entrySummary} numberOfLines={3}>
                  {item.summary}
                </Text>
                <View style={styles.entryCardFooter}>
                  <Text style={styles.entryDate}>
                    {new Date(item.created_at).toLocaleDateString()}
                  </Text>
                  {item.read && <Text style={styles.readText}>Read</Text>}
                </View>
              </TouchableOpacity>
            )}
            ListEmptyComponent={
              <View style={styles.emptyContainer}>
                <Text style={styles.emptyText}>No knowledge entries found</Text>
              </View>
            }
          />
        </View>
      ) : activeTab === 'sources' ? (
        <FlatList
          data={sources}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <View style={styles.sourceCard}>
              <View style={styles.sourceHeader}>
                <Text style={styles.sourceName}>{item.name}</Text>
                <View style={[styles.activeBadge, !item.is_active && styles.inactiveBadge]}>
                  <Text style={[styles.activeBadgeText, !item.is_active && styles.inactiveBadgeText]}>
                    {item.is_active ? 'Active' : 'Inactive'}
                  </Text>
                </View>
              </View>
              <Text style={styles.sourceUrl} numberOfLines={1}>{item.url}</Text>
              <Text style={styles.sourceMeta}>
                Category: {item.category || 'Uncategorized'}
              </Text>
              <Text style={styles.sourceMeta}>
                Last fetched: {item.last_fetched_at ? new Date(item.last_fetched_at).toLocaleString() : 'Never'}
              </Text>
              
              <TouchableOpacity 
                style={styles.syncButton} 
                onPress={() => handleRefreshSource(item.id)}
              >
                <Text style={styles.syncButtonText}>Sync Feed</Text>
              </TouchableOpacity>
            </View>
          )}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>No feed sources registered yet</Text>
            </View>
          }
        />
      ) : (
        <ScrollView contentContainerStyle={styles.formContainer}>
          <Text style={styles.formLabel}>Source Name</Text>
          <TextInput
            style={styles.formInput}
            placeholder="e.g. TechCrunch AI"
            placeholderTextColor={colors.slate[400]}
            value={formName}
            onChangeText={setFormName}
          />

          <Text style={styles.formLabel}>Feed URL</Text>
          <TextInput
            style={styles.formInput}
            placeholder="e.g. https://techcrunch.com/feed"
            placeholderTextColor={colors.slate[400]}
            value={formUrl}
            onChangeText={setFormUrl}
            autoCapitalize="none"
            keyboardType="url"
          />

          <Text style={styles.formLabel}>Category</Text>
          <TextInput
            style={styles.formInput}
            placeholder="e.g. AI News"
            placeholderTextColor={colors.slate[400]}
            value={formCategory}
            onChangeText={setFormCategory}
          />

          <TouchableOpacity 
            style={[styles.submitButton, submitting && styles.disabledButton]} 
            onPress={handleAddSource}
            disabled={submitting}
          >
            {submitting ? (
              <ActivityIndicator color={colors.white} size="small" />
            ) : (
              <Text style={styles.submitButtonText}>Add Feed Source</Text>
            )}
          </TouchableOpacity>
        </ScrollView>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.slate[50],
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.slate[50],
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    backgroundColor: colors.white,
    borderBottomWidth: 1,
    borderBottomColor: colors.slate[200],
  },
  backButton: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
  },
  backButtonText: {
    color: colors.indigo[600],
    fontSize: fontSize.md,
    fontWeight: '600',
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
  tabsContainer: {
    flexDirection: 'row',
    backgroundColor: colors.white,
    borderBottomWidth: 1,
    borderBottomColor: colors.slate[200],
  },
  tabButton: {
    flex: 1,
    paddingVertical: spacing.md,
    alignItems: 'center',
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  activeTabButton: {
    borderBottomColor: colors.indigo[600],
  },
  tabButtonText: {
    fontSize: fontSize.xs,
    color: colors.slate[500],
    fontWeight: '600',
  },
  activeTabButtonText: {
    color: colors.indigo[600],
  },
  list: {
    padding: spacing.lg,
  },
  entryCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.slate[200],
    shadowColor: colors.slate[900],
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 2,
  },
  entryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  entryCategory: {
    fontSize: fontSize.xs,
    color: colors.indigo[600],
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  entrySource: {
    fontSize: fontSize.xs,
    color: colors.slate[400],
    fontWeight: '500',
  },
  entryTitle: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.slate[900],
    marginBottom: spacing.xs,
  },
  readTitle: {
    color: colors.slate[500],
    fontWeight: '500',
  },
  entrySummary: {
    fontSize: fontSize.sm,
    color: colors.slate[600],
    lineHeight: 18,
    marginBottom: spacing.sm,
  },
  entryCardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  entryDate: {
    fontSize: fontSize.xs,
    color: colors.slate[400],
  },
  readText: {
    fontSize: fontSize.xs,
    color: colors.emerald[600],
    fontWeight: '600',
  },
  importanceBadge: {
    backgroundColor: colors.slate[100],
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  importanceHigh: {
    backgroundColor: colors.red[100],
  },
  importanceText: {
    fontSize: 10,
    color: colors.slate[600],
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  importanceHighText: {
    color: colors.red[700],
  },
  sourceCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.slate[200],
  },
  sourceHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  sourceName: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.slate[900],
  },
  sourceUrl: {
    fontSize: fontSize.xs,
    color: colors.indigo[600],
    marginBottom: spacing.sm,
  },
  sourceMeta: {
    fontSize: fontSize.xs,
    color: colors.slate[500],
    marginBottom: 2,
  },
  activeBadge: {
    backgroundColor: colors.emerald[100],
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.full,
  },
  inactiveBadge: {
    backgroundColor: colors.slate[100],
  },
  activeBadgeText: {
    fontSize: 10,
    color: colors.emerald[700],
    fontWeight: '700',
  },
  inactiveBadgeText: {
    color: colors.slate[600],
  },
  syncButton: {
    alignSelf: 'flex-start',
    backgroundColor: colors.indigo[50],
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.md,
    marginTop: spacing.md,
  },
  syncButtonText: {
    color: colors.indigo[700],
    fontSize: fontSize.xs,
    fontWeight: '600',
  },
  searchBarContainer: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    backgroundColor: colors.white,
  },
  searchInput: {
    backgroundColor: colors.slate[50],
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: fontSize.sm,
    color: colors.slate[900],
    borderWidth: 1,
    borderColor: colors.slate[200],
  },
  categoriesContainer: {
    backgroundColor: colors.white,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.slate[200],
  },
  categoryChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    backgroundColor: colors.slate[100],
    marginRight: spacing.sm,
  },
  activeCategoryChip: {
    backgroundColor: colors.indigo[600],
  },
  categoryChipText: {
    fontSize: fontSize.xs,
    color: colors.slate[600],
    fontWeight: '600',
  },
  activeCategoryChipText: {
    color: colors.white,
  },
  detailScroll: {
    padding: spacing.lg,
    backgroundColor: colors.white,
  },
  detailCategory: {
    fontSize: fontSize.xs,
    color: colors.indigo[600],
    fontWeight: '700',
    textTransform: 'uppercase',
    marginBottom: spacing.xs,
  },
  detailTitle: {
    fontSize: fontSize.xl,
    fontWeight: '800',
    color: colors.slate[900],
    lineHeight: 28,
    marginBottom: spacing.xs,
  },
  detailSource: {
    fontSize: fontSize.xs,
    color: colors.slate[500],
    marginBottom: spacing.lg,
  },
  sectionContainer: {
    marginBottom: spacing.lg,
    backgroundColor: colors.slate[50],
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.slate[200],
  },
  sectionTitle: {
    fontSize: fontSize.sm,
    fontWeight: '700',
    color: colors.slate[900],
    marginBottom: spacing.xs,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  summaryText: {
    fontSize: fontSize.sm,
    color: colors.slate[700],
    lineHeight: 20,
  },
  contentText: {
    fontSize: fontSize.sm,
    color: colors.slate[800],
    lineHeight: 22,
  },
  detailUrl: {
    fontSize: fontSize.xs,
    color: colors.indigo[600],
    marginBottom: spacing.lg,
    textDecorationLine: 'underline',
  },
  markReadButton: {
    backgroundColor: colors.indigo[600],
    borderRadius: borderRadius.lg,
    paddingVertical: spacing.md,
    alignItems: 'center',
    marginTop: spacing.sm,
    marginBottom: spacing.xl,
  },
  markReadButtonText: {
    color: colors.white,
    fontSize: fontSize.md,
    fontWeight: '700',
  },
  formContainer: {
    padding: spacing.lg,
  },
  formLabel: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.slate[800],
    marginBottom: spacing.xs,
  },
  formInput: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.slate[200],
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: fontSize.sm,
    color: colors.slate[900],
    marginBottom: spacing.lg,
  },
  submitButton: {
    backgroundColor: colors.indigo[600],
    borderRadius: borderRadius.lg,
    paddingVertical: spacing.md,
    alignItems: 'center',
    marginTop: spacing.md,
  },
  disabledButton: {
    backgroundColor: colors.slate[400],
  },
  submitButtonText: {
    color: colors.white,
    fontSize: fontSize.md,
    fontWeight: '700',
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
