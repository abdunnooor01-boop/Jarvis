import React, { useEffect, useState, useCallback } from 'react';
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
  RefreshControl,
} from 'react-native';
import api from '../services/api';
import { TaskTemplate, FreelanceJob, FreelanceOrderResponse } from '../types/api';
import { colors, borderRadius, fontSize, spacing } from '../utils/theme';

type ScreenView = 'list' | 'detail' | 'order' | 'submit';
type JobsTab = 'accepted' | 'in_progress' | 'completed';

const FreelanceScreen = () => {
  const [templates, setTemplates] = useState<TaskTemplate[]>([]);
  const [jobs, setJobs] = useState<FreelanceJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTab, setSelectedTab] = useState<'templates' | 'jobs'>('templates');
  const [jobsTab, setJobsTab] = useState<JobsTab>('accepted');
  const [view, setView] = useState<ScreenView>('list');

  const [selectedTemplate, setSelectedTemplate] = useState<TaskTemplate | null>(null);
  const [selectedJob, setSelectedJob] = useState<FreelanceJob | null>(null);

  const [customerEmail, setCustomerEmail] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [instructions, setInstructions] = useState('');
  const [submittingOrder, setSubmittingOrder] = useState(false);
  const [orderResult, setOrderResult] = useState<FreelanceOrderResponse | null>(null);
  const [earnings, setEarnings] = useState({ total: 0, pending: 0 });

  useEffect(() => { loadData(); }, []);

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
      const total = jobsData.reduce((s: number, j: FreelanceJob) => {
        const a = j.amount_cents || j.price_cents || 0;
        return j.status === 'completed' || j.status === 'paid' ? s + a : s;
      }, 0);
      const pending = jobsData.reduce((s: number, j: FreelanceJob) => {
        const a = j.amount_cents || j.price_cents || 0;
        return j.status === 'pending' || j.status === 'paid' ? s + a : s;
      }, 0);
      setEarnings({ total, pending });
    } catch (err: any) {
      setError(err.detail || 'Failed to load freelance data');
    } finally { setLoading(false); }
  };

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, []);

  const formatPrice = (cents: number) => `$${(cents / 100).toFixed(2)}`;

  const handleTemplatePress = (t: TaskTemplate) => {
    setSelectedTemplate(t);
    setView('detail');
  };

  const handleAcceptTask = () => {
    setView('order');
    setCustomerEmail('');
    setCustomerName('');
    setInstructions('');
    setOrderResult(null);
  };

  const handleSubmitOrder = async () => {
    if (!selectedTemplate) return;
    if (!customerEmail.trim()) { Alert.alert('Required', 'Please enter your email'); return; }
    setSubmittingOrder(true);
    try {
      const result = await api.createOrder({
        template_id: selectedTemplate.id,
        description: instructions || selectedTemplate.description,
        customer_email: customerEmail.trim(),
        customer_name: customerName.trim() || undefined,
      });
      setOrderResult(result);
      Alert.alert('Order Created!', `Amount: ${formatPrice(result.amount_cents)}. ${result.stripe_payment_link ? 'Complete payment to start.' : ''}`);
      setJobs(await api.listJobs());
    } catch (err: any) {
      Alert.alert('Error', err.detail || 'Failed to create order');
    } finally { setSubmittingOrder(false); }
  };

  const handleJobPress = (job: FreelanceJob) => {
    setSelectedJob(job);
    setView('submit');
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return colors.green[500];
      case 'paid': case 'in_progress': return colors.indigo[600];
      case 'pending': return colors.amber[500];
      default: return colors.slate[400];
    }
  };

  const filteredJobs = jobs.filter((j: FreelanceJob) => {
    if (jobsTab === 'accepted') return j.status === 'pending' || j.status === 'paid';
    if (jobsTab === 'in_progress') return j.status === 'in_progress';
    if (jobsTab === 'completed') return j.status === 'completed';
    return true;
  });

  const statusCounts = {
    accepted: jobs.filter((j: FreelanceJob) => j.status === 'pending' || j.status === 'paid').length,
    in_progress: jobs.filter((j: FreelanceJob) => j.status === 'in_progress').length,
    completed: jobs.filter((j: FreelanceJob) => j.status === 'completed').length,
  };

  // Detail View
  if (view === 'detail' && selectedTemplate) {
    return (
      <ScrollView style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => { setView('list'); setSelectedTemplate(null); }}>
            <Text style={styles.backButton}>← Back</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.detailSection}>
          <Text style={styles.detailName}>{selectedTemplate.name}</Text>
          <Text style={styles.detailPrice}>{formatPrice(selectedTemplate.price_cents)}</Text>
          <Text style={styles.detailCategory}>{selectedTemplate.category.toUpperCase()}</Text>
          <View style={styles.divider} />
          <Text style={styles.detailLabel}>Description</Text>
          <Text style={styles.detailText}>{selectedTemplate.description}</Text>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Est. Time</Text>
            <Text style={styles.detailValue}>{selectedTemplate.estimated_minutes} min</Text>
          </View>
          {selectedTemplate.required_capabilities?.length ? (
            <>
              <Text style={styles.detailLabel}>Requirements</Text>
              <View style={styles.requirementsList}>
                {selectedTemplate.required_capabilities.map((cap, i) => (
                  <View key={i} style={styles.requirementBadge}>
                    <Text style={styles.requirementText}>{cap.replace(/_/g, ' ')}</Text>
                  </View>
                ))}
              </View>
            </>
          ) : null}
          <TouchableOpacity style={styles.acceptButton} onPress={handleAcceptTask}>
            <Text style={styles.acceptButtonText}>Accept — {formatPrice(selectedTemplate.price_cents)}</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    );
  }

  // Order Form
  if (view === 'order' && selectedTemplate) {
    return (
      <ScrollView style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => { setView('detail'); }}>
            <Text style={styles.backButton}>← Back</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.detailSection}>
          <Text style={styles.detailName}>Order: {selectedTemplate.name}</Text>
          <Text style={styles.detailPrice}>{formatPrice(selectedTemplate.price_cents)}</Text>
          <View style={styles.divider} />
          {orderResult ? (
            <View style={styles.orderResultCard}>
              <Text style={styles.orderResultTitle}>Order Created!</Text>
              <Text style={styles.orderResultId}>ID: {orderResult.job_id.slice(0, 8)}...</Text>
              <Text style={styles.orderResultAmount}>Amount: {formatPrice(orderResult.amount_cents)}</Text>
              <Text style={styles.orderResultStatus}>Status: {orderResult.status}</Text>
              {orderResult.stripe_payment_link ? (
                <Text style={styles.orderResultLink}>Payment: {orderResult.stripe_payment_link}</Text>
              ) : null}
              <TouchableOpacity style={styles.acceptButton} onPress={() => { setView('list'); setSelectedTemplate(null); setOrderResult(null); }}>
                <Text style={styles.acceptButtonText}>Done</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <>
              <Text style={styles.formLabel}>Email *</Text>
              <TextInput style={styles.formInput} value={customerEmail} onChangeText={setCustomerEmail} placeholder="your@email.com" placeholderTextColor={colors.slate[400]} keyboardType="email-address" autoCapitalize="none" />
              <Text style={styles.formLabel}>Name</Text>
              <TextInput style={styles.formInput} value={customerName} onChangeText={setCustomerName} placeholder="Your name" placeholderTextColor={colors.slate[400]} />
              <Text style={styles.formLabel}>Instructions (optional)</Text>
              <TextInput style={[styles.formInput, styles.formTextArea]} value={instructions} onChangeText={setInstructions} placeholder="Any specific requirements..." placeholderTextColor={colors.slate[400]} multiline numberOfLines={4} />
              <TouchableOpacity style={[styles.acceptButton, submittingOrder && { opacity: 0.5 }]} onPress={handleSubmitOrder} disabled={submittingOrder}>
                <Text style={styles.acceptButtonText}>{submittingOrder ? 'Creating...' : `Place Order — ${formatPrice(selectedTemplate.price_cents)}`}</Text>
              </TouchableOpacity>
            </>
          )}
        </View>
      </ScrollView>
    );
  }

  // Job Detail View
  if (view === 'submit' && selectedJob) {
    const isCompleted = selectedJob.status === 'completed';
    return (
      <ScrollView style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => { setView('list'); setSelectedJob(null); }}>
            <Text style={styles.backButton}>← Back</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.detailSection}>
          <Text style={styles.detailName}>{selectedJob.template_name || 'Task'}</Text>
          <View style={styles.statusRow}>
            <View style={[styles.statusDot, { backgroundColor: getStatusColor(selectedJob.status) }]} />
            <Text style={styles.statusLabel}>{selectedJob.status.replace(/_/g, ' ')}</Text>
          </View>
          <Text style={styles.detailPrice}>{formatPrice(selectedJob.amount_cents || selectedJob.price_cents || 0)}</Text>
          <View style={styles.divider} />
          {selectedJob.description ? (
            <><Text style={styles.detailLabel}>Description</Text><Text style={styles.detailText}>{selectedJob.description}</Text></>
          ) : null}
          {selectedJob.result_summary ? (
            <><Text style={styles.detailLabel}>Result</Text><Text style={styles.detailText}>{selectedJob.result_summary}</Text></>
          ) : null}
          {selectedJob.result_files && Object.keys(selectedJob.result_files).length > 0 ? (
            <><Text style={styles.detailLabel}>Deliverables</Text>
              {Object.entries(selectedJob.result_files).map(([name, url]) => (
                <TouchableOpacity key={name} style={styles.fileRow}>
                  <Text style={styles.fileName}>{name}</Text>
                  <Text style={styles.fileUrl}>View</Text>
                </TouchableOpacity>
              ))}
            </>
          ) : null}
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Created</Text>
            <Text style={styles.detailValue}>{new Date(selectedJob.created_at).toLocaleDateString()}</Text>
          </View>
          {selectedJob.completed_at ? (
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Completed</Text>
              <Text style={styles.detailValue}>{new Date(selectedJob.completed_at).toLocaleDateString()}</Text>
            </View>
          ) : null}
          {selectedJob.stripe_payment_link && !isCompleted ? (
            <TouchableOpacity style={styles.acceptButton}>
              <Text style={styles.acceptButtonText}>Complete Payment</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      </ScrollView>
    );
  }

  // Main List View
  if (loading && !refreshing) {
    return <View style={styles.center}><ActivityIndicator size="large" color={colors.indigo[600]} /></View>;
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
        <Text style={styles.title}>Freelance Tasks</Text>
        <Text style={styles.subtitle}>Earn by completing tasks</Text>
      </View>

      {/* Earnings Summary */}
      <View style={styles.earningsCard}>
        <Text style={styles.earningsTitle}>Earnings Summary</Text>
        <View style={styles.earningsRow}>
          <View style={styles.earningsItem}>
            <Text style={styles.earningsValue}>{formatPrice(earnings.total)}</Text>
            <Text style={styles.earningsLabel}>Earned</Text>
          </View>
          <View style={styles.earningsDivider} />
          <View style={styles.earningsItem}>
            <Text style={styles.earningsValue}>{formatPrice(earnings.pending)}</Text>
            <Text style={styles.earningsLabel}>Pending</Text>
          </View>
          <View style={styles.earningsDivider} />
          <View style={styles.earningsItem}>
            <Text style={[styles.earningsValue, { color: colors.indigo[600] }]}>{jobs.length}</Text>
            <Text style={styles.earningsLabel}>Jobs</Text>
          </View>
        </View>
      </View>

      {/* Main Tabs */}
      <View style={styles.tabs}>
        <TouchableOpacity style={[styles.tab, selectedTab === 'templates' && styles.activeTab]} onPress={() => setSelectedTab('templates')}>
          <Text style={[styles.tabText, selectedTab === 'templates' && styles.activeTabText]}>Available Tasks</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.tab, selectedTab === 'jobs' && styles.activeTab]} onPress={() => setSelectedTab('jobs')}>
          <Text style={[styles.tabText, selectedTab === 'jobs' && styles.activeTabText]}>My Tasks</Text>
        </TouchableOpacity>
      </View>

      {selectedTab === 'templates' ? (
        <FlatList
          data={templates}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          renderItem={({ item }) => (
            <TouchableOpacity onPress={() => handleTemplatePress(item)}>
              <View style={styles.card}>
                <View style={styles.cardHeader}>
                  <Text style={styles.cardName}>{item.name}</Text>
                  <Text style={styles.cardPrice}>{formatPrice(item.price_cents)}</Text>
                </View>
                <Text style={styles.cardCategory}>{item.category}</Text>
                <Text style={styles.cardDescription} numberOfLines={2}>{item.description}</Text>
                <Text style={styles.cardDuration}>Est. {item.estimated_minutes} min</Text>
              </View>
            </TouchableOpacity>
          )}
          ListEmptyComponent={<Text style={styles.emptyText}>No tasks available</Text>}
        />
      ) : (
        <>
          <View style={styles.jobsTabs}>
            {(['accepted', 'in_progress', 'completed'] as JobsTab[]).map((tab) => (
              <TouchableOpacity key={tab} style={[styles.jobsTab, jobsTab === tab && styles.jobsTabActive]} onPress={() => setJobsTab(tab)}>
                <Text style={[styles.jobsTabText, jobsTab === tab && styles.jobsTabTextActive]}>
                  {tab.replace(/_/g, ' ')} ({statusCounts[tab]})
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          <FlatList
            data={filteredJobs}
            keyExtractor={(item) => item.id}
            contentContainerStyle={styles.list}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
            renderItem={({ item }) => (
              <TouchableOpacity onPress={() => handleJobPress(item)}>
                <View style={styles.card}>
                  <View style={styles.cardHeader}>
                    <Text style={styles.cardName}>{item.template_name || 'Custom Task'}</Text>
                    <View style={[styles.statusBadge, { backgroundColor: getStatusColor(item.status) + '20' }]}>
                      <Text style={[styles.statusText, { color: getStatusColor(item.status) }]}>{item.status.replace(/_/g, ' ')}</Text>
                    </View>
                  </View>
                  <Text style={styles.cardPrice}>{formatPrice(item.amount_cents || item.price_cents || 0)}</Text>
                  <Text style={styles.cardDate}>{new Date(item.created_at).toLocaleDateString()}</Text>
                </View>
              </TouchableOpacity>
            )}
            ListEmptyComponent={<Text style={styles.emptyText}>No {jobsTab.replace(/_/g, ' ')} tasks</Text>}
          />
        </>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.white },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.white },
  header: { paddingHorizontal: spacing.lg, paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.slate[200] },
  title: { fontSize: fontSize.lg, fontWeight: '700', color: colors.slate[900] },
  subtitle: { fontSize: fontSize.sm, color: colors.slate[500], marginTop: 2 },
  backButton: { fontSize: fontSize.md, color: colors.indigo[600], fontWeight: '600' },
  earningsCard: { marginHorizontal: spacing.lg, marginTop: spacing.md, backgroundColor: colors.slate[50], borderRadius: borderRadius.lg, padding: spacing.lg, borderWidth: 1, borderColor: colors.slate[200] },
  earningsTitle: { fontSize: fontSize.xs, fontWeight: '600', color: colors.slate[500], textTransform: 'uppercase', marginBottom: spacing.md },
  earningsRow: { flexDirection: 'row', alignItems: 'center' },
  earningsItem: { flex: 1, alignItems: 'center' },
  earningsValue: { fontSize: fontSize['2xl'], fontWeight: '700', color: colors.green[600] },
  earningsLabel: { fontSize: fontSize.xs, color: colors.slate[500], marginTop: 2 },
  earningsDivider: { width: 1, height: 36, backgroundColor: colors.slate[200] },
  tabs: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: colors.slate[200] },
  tab: { flex: 1, paddingVertical: spacing.md, alignItems: 'center', borderBottomWidth: 2, borderBottomColor: 'transparent' },
  activeTab: { borderBottomColor: colors.indigo[600] },
  tabText: { fontSize: fontSize.md, fontWeight: '500', color: colors.slate[500] },
  activeTabText: { color: colors.indigo[600], fontWeight: '600' },
  jobsTabs: { flexDirection: 'row', paddingHorizontal: spacing.md, paddingVertical: spacing.sm, backgroundColor: colors.slate[50], borderBottomWidth: 1, borderBottomColor: colors.slate[200] },
  jobsTab: { flex: 1, paddingVertical: spacing.sm, alignItems: 'center', borderRadius: borderRadius.md, marginHorizontal: 2 },
  jobsTabActive: { backgroundColor: colors.indigo[100] },
  jobsTabText: { fontSize: fontSize.xs, fontWeight: '600', color: colors.slate[600] },
  jobsTabTextActive: { color: colors.indigo[700] },
  list: { padding: spacing.lg },
  card: { backgroundColor: colors.slate[50], borderRadius: borderRadius.lg, padding: spacing.lg, marginBottom: spacing.md, borderWidth: 1, borderColor: colors.slate[200] },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.xs },
  cardName: { fontSize: fontSize.md, fontWeight: '600', color: colors.slate[900], flex: 1 },
  cardPrice: { fontSize: fontSize.md, fontWeight: '700', color: colors.indigo[600] },
  cardCategory: { fontSize: fontSize.xs, color: colors.indigo[600], fontWeight: '600', textTransform: 'uppercase', marginBottom: spacing.xs },
  cardDescription: { fontSize: fontSize.sm, color: colors.slate[600], lineHeight: 18, marginBottom: spacing.sm },
  cardDuration: { fontSize: fontSize.xs, color: colors.slate[400] },
  cardDate: { fontSize: fontSize.xs, color: colors.slate[400], marginTop: spacing.xs },
  statusBadge: { borderRadius: borderRadius.full, paddingHorizontal: spacing.md, paddingVertical: 2 },
  statusText: { fontSize: fontSize.xs, fontWeight: '600', textTransform: 'capitalize' },
  detailSection: { padding: spacing.lg },
  detailName: { fontSize: fontSize['2xl'], fontWeight: '700', color: colors.slate[900], marginBottom: spacing.xs },
  detailPrice: { fontSize: fontSize['3xl'], fontWeight: '700', color: colors.indigo[600], marginBottom: spacing.xs },
  detailCategory: { fontSize: fontSize.xs, color: colors.indigo[600], fontWeight: '600', textTransform: 'uppercase', marginBottom: spacing.md },
  divider: { height: 1, backgroundColor: colors.slate[200], marginVertical: spacing.lg },
  detailLabel: { fontSize: fontSize.xs, fontWeight: '600', color: colors.slate[500], textTransform: 'uppercase', marginBottom: spacing.xs, marginTop: spacing.md },
  detailText: { fontSize: fontSize.md, color: colors.slate[700], lineHeight: 22 },
  detailValue: { fontSize: fontSize.md, color: colors.slate[900], fontWeight: '500' },
  detailRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: spacing.md },
  statusRow: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.sm },
  statusDot: { width: 8, height: 8, borderRadius: 4, marginRight: spacing.sm },
  statusLabel: { fontSize: fontSize.sm, color: colors.slate[600], textTransform: 'capitalize' },
  requirementsList: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginTop: spacing.sm },
  requirementBadge: { backgroundColor: colors.indigo[50], borderRadius: borderRadius.full, paddingHorizontal: spacing.md, paddingVertical: spacing.xs, borderWidth: 1, borderColor: colors.indigo[200] },
  requirementText: { fontSize: fontSize.xs, color: colors.indigo[700], fontWeight: '500', textTransform: 'capitalize' },
  acceptButton: { backgroundColor: colors.indigo[600], borderRadius: borderRadius.lg, paddingVertical: spacing.lg, alignItems: 'center', marginTop: spacing['2xl'] },
  acceptButtonText: { color: colors.white, fontSize: fontSize.lg, fontWeight: '700' },
  formLabel: { fontSize: fontSize.sm, fontWeight: '600', color: colors.slate[700], marginTop: spacing.lg, marginBottom: spacing.sm },
  formInput: { backgroundColor: colors.slate[50], borderWidth: 1, borderColor: colors.slate[200], borderRadius: borderRadius.lg, paddingHorizontal: spacing.lg, paddingVertical: spacing.md, fontSize: fontSize.md, color: colors.slate[900] },
  formTextArea: { minHeight: 100, textAlignVertical: 'top' },
  orderResultCard: { backgroundColor: colors.green[500] + '10', borderRadius: borderRadius.lg, padding: spacing['2xl'], borderWidth: 1, borderColor: colors.green[500] + '30', alignItems: 'center' },
  orderResultTitle: { fontSize: fontSize.xl, fontWeight: '700', color: colors.green[600], marginBottom: spacing.md },
  orderResultId: { fontSize: fontSize.sm, color: colors.slate[600], marginBottom: spacing.xs },
  orderResultAmount: { fontSize: fontSize.md, fontWeight: '600', color: colors.slate[900], marginBottom: spacing.xs },
  orderResultStatus: { fontSize: fontSize.sm, color: colors.slate[600], marginBottom: spacing.xs },
  orderResultLink: { fontSize: fontSize.sm, color: colors.indigo[600], marginBottom: spacing.lg, textAlign: 'center' },
  fileRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.slate[100] },
  fileName: { fontSize: fontSize.sm, color: colors.slate[700], fontWeight: '500' },
  fileUrl: { fontSize: fontSize.sm, color: colors.indigo[600] },
  emptyText: { textAlign: 'center', color: colors.slate[400], padding: spacing['3xl'], fontSize: fontSize.md },
  errorText: { fontSize: fontSize.md, color: colors.red[500], marginBottom: spacing.lg },
  retryButton: { backgroundColor: colors.indigo[600], borderRadius: borderRadius.lg, paddingHorizontal: spacing['2xl'], paddingVertical: spacing.md },
  retryButtonText: { color: colors.white, fontSize: fontSize.md, fontWeight: '600' },
});

export default FreelanceScreen;