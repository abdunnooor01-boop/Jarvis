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
  Image,
} from 'react-native';
import api from '../services/api';
import { TestPlan, TestRun, TestingSubscription, TestStepResult } from '../types/api';
import { colors, borderRadius, fontSize, spacing } from '../utils/theme';

type TabType = 'plans' | 'runs' | 'subscription';

const TestingScreen = () => {
  const [activeTab, setActiveTab] = useState<TabType>('plans');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Saas Testing states
  const [plans, setPlans] = useState<TestPlan[]>([]);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [subscription, setSubscription] = useState<TestingSubscription | null>(null);

  // Detail views state
  const [selectedRun, setSelectedRun] = useState<TestRun | null>(null);
  const [viewingPlanId, setViewPlanId] = useState<string | null>(null);

  // Create/Edit plan modal form state
  const [showPlanForm, setShowPlanForm] = useState(false);
  const [editingPlan, setEditingPlan] = useState<TestPlan | null>(null);
  const [formName, setFormName] = useState('');
  const [formUrl, setFormUrl] = useState('');
  const [formCriteria, setFormCriteria] = useState('');
  const [formSchedule, setFormSchedule] = useState<'manual' | 'daily' | 'weekly'>('manual');
  const [submittingPlan, setSubmittingPlan] = useState(false);

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeTab === 'plans') {
        const plansData = await api.listTestPlans();
        const normalizedPlans = Array.isArray(plansData) ? plansData : (plansData as any).items || [];
        setPlans(normalizedPlans);
      } else if (activeTab === 'runs') {
        const runsData = await api.listTestRuns();
        const normalizedRuns = Array.isArray(runsData) ? runsData : (runsData as any).items || [];
        setRuns(normalizedRuns);
      } else if (activeTab === 'subscription') {
        const subData = await api.getTestingSubscription();
        setSubscription(subData);
      }
    } catch (err: any) {
      setError(err.detail || err.message || 'Failed to load testing data');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateOrEditPlan = async () => {
    if (!formName || !formUrl || !formCriteria) {
      Alert.alert('Error', 'Please fill in all required fields');
      return;
    }
    setSubmittingPlan(true);
    try {
      const payload = {
        name: formName,
        url: formUrl,
        test_criteria: formCriteria,
        schedule: formSchedule,
      };

      if (editingPlan) {
        await api.editTestPlan(editingPlan.id, payload);
        Alert.alert('Success', 'Test plan updated successfully!');
      } else {
        await api.createTestPlan(payload);
        Alert.alert('Success', 'Test plan created successfully!');
      }

      setFormName('');
      setFormUrl('');
      setFormCriteria('');
      setFormSchedule('manual');
      setEditingPlan(null);
      setShowPlanForm(false);
      loadData();
    } catch (err: any) {
      Alert.alert('Error', err.detail || err.message || 'Failed to save test plan');
    } finally {
      setSubmittingPlan(false);
    }
  };

  const startEditPlan = (plan: TestPlan) => {
    setEditingPlan(plan);
    setFormName(plan.name || '');
    setFormUrl(plan.url || '');
    setFormCriteria((plan as any).test_criteria || '');
    setFormSchedule((plan as any).schedule || 'manual');
    setShowPlanForm(true);
  };

  const handleTriggerRun = async (planId: string) => {
    try {
      Alert.alert('Triggering', 'Starting test execution run...');
      await api.triggerTestPlanRun(planId);
      Alert.alert('Success', 'Test run triggered! Check the Runs tab to view progress.');
    } catch (err: any) {
      Alert.alert('Error', err.detail || err.message || 'Failed to trigger run');
    }
  };

  const handleSubscribe = async (tier: 'basic' | 'pro') => {
    try {
      Alert.alert('Redirecting', `Creating Stripe Checkout session for ${tier.toUpperCase()} tier...`);
      const checkoutData = await api.subscribeToTesting(tier);
      if (checkoutData && checkoutData.checkout_url) {
        Alert.alert('Subscription Link', `Please checkout here:\n${checkoutData.checkout_url}`);
      } else {
        Alert.alert('Mock Success', `Mock subscription activated successfully for ${tier.toUpperCase()}!`);
        loadData();
      }
    } catch (err: any) {
      Alert.alert('Error', err.detail || err.message || 'Subscription failed');
    }
  };

  const renderPlanItem = ({ item }: { item: TestPlan }) => (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Text style={styles.cardTitle}>{item.name || 'Untitled Plan'}</Text>
        <View style={[styles.statusBadge, item.status === 'active' ? styles.statusActive : styles.statusInactive]}>
          <Text style={styles.statusText}>{item.status}</Text>
        </View>
      </View>
      <Text style={styles.cardUrl} numberOfLines={1}>{item.url}</Text>
      <Text style={styles.cardMeta}>Schedule: {(item as any).schedule || 'manual'}</Text>
      <Text style={styles.cardMeta}>
        Pass Rate: {item.pass_rate !== undefined && item.pass_rate !== null ? `${Math.round(item.pass_rate * 100)}%` : 'N/A'}
      </Text>

      <View style={styles.actionRow}>
        <TouchableOpacity style={styles.actionButton} onPress={() => startEditPlan(item)}>
          <Text style={styles.actionButtonText}>Edit</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.actionButton, styles.triggerButton]} onPress={() => handleTriggerRun(item.id)}>
          <Text style={styles.triggerButtonText}>Trigger Run</Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderRunItem = ({ item }: { item: TestRun }) => (
    <TouchableOpacity style={styles.card} onPress={() => setSelectedRun(item)}>
      <View style={styles.cardHeader}>
        <Text style={styles.cardTitle}>{item.name || `Run for ${item.plan_url || 'Plan'}`}</Text>
        <View style={[
          styles.statusBadge,
          item.status === 'passed' ? styles.statusActive : 
          item.status === 'failed' ? styles.statusFailed : 
          styles.statusRunning
        ]}>
          <Text style={styles.statusText}>{item.status.toUpperCase()}</Text>
        </View>
      </View>
      <Text style={styles.cardUrl} numberOfLines={1}>{item.url}</Text>
      <View style={styles.statsRow}>
        <Text style={styles.statText}>Passed: {item.passed_count}</Text>
        <Text style={[styles.statText, item.failed_count > 0 && styles.statFailed]}>Failed: {item.failed_count}</Text>
      </View>
      <Text style={styles.cardMeta}>Date: {new Date(item.created_at).toLocaleString()}</Text>
    </TouchableOpacity>
  );

  if (selectedRun) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => setSelectedRun(null)} style={styles.backButton}>
            <Text style={styles.backButtonText}>← Back</Text>
          </TouchableOpacity>
          <Text style={styles.title} numberOfLines={1}>Run Details</Text>
          <View style={{ width: 60 }} />
        </View>

        <ScrollView contentContainerStyle={styles.detailScroll}>
          <View style={[styles.statusBanner, selectedRun.status === 'passed' ? styles.bannerPassed : selectedRun.status === 'failed' ? styles.bannerFailed : styles.bannerRunning]}>
            <Text style={styles.bannerText}>Status: {selectedRun.status.toUpperCase()}</Text>
          </View>

          <Text style={styles.detailTitle}>{selectedRun.name || 'Test Execution Run'}</Text>
          <Text style={styles.detailUrl}>Target URL: {selectedRun.url}</Text>
          <Text style={styles.cardMeta}>Started: {new Date(selectedRun.created_at).toLocaleString()}</Text>
          <Text style={styles.cardMeta}>Duration: {selectedRun.duration ? `${selectedRun.duration}s` : 'N/A'}</Text>

          <View style={styles.divider} />

          {selectedRun.error_message ? (
            <View style={styles.errorContainer}>
              <Text style={styles.errorTitle}>Error Message</Text>
              <Text style={styles.errorBody}>{selectedRun.error_message}</Text>
            </View>
          ) : null}

          <Text style={styles.sectionTitle}>Verification Steps ({selectedRun.results?.length || 0})</Text>
          
          {(selectedRun.results || []).map((step, idx) => (
            <View key={step.id || idx.toString()} style={styles.stepCard}>
              <View style={styles.stepHeader}>
                <Text style={styles.stepNumber}>Step {idx + 1}</Text>
                <View style={[styles.miniBadge, step.status === 'passed' ? styles.miniPassed : styles.miniFailed]}>
                  <Text style={styles.miniText}>{step.status.toUpperCase()}</Text>
                </View>
              </View>
              <Text style={styles.stepCriterion}>{step.name}</Text>
              {step.error ? (
                <Text style={styles.stepError}>Error: {step.error}</Text>
              ) : null}
            </View>
          ))}

          {selectedRun.screenshots && selectedRun.screenshots.length > 0 ? (
            <View style={{ marginTop: spacing.lg }}>
              <Text style={styles.sectionTitle}>Screenshots</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.screenshotsScroll}>
                {selectedRun.screenshots.map((url, i) => (
                  <View key={i.toString()} style={styles.screenshotWrapper}>
                    <Image source={{ uri: url }} style={styles.screenshot} resizeMode="contain" />
                  </View>
                ))}
              </ScrollView>
            </View>
          ) : null}
        </ScrollView>
      </View>
    );
  }

  if (showPlanForm) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => setShowPlanForm(false)} style={styles.backButton}>
            <Text style={styles.backButtonText}>← Cancel</Text>
          </TouchableOpacity>
          <Text style={styles.title}>{editingPlan ? 'Edit Test Plan' : 'Create Test Plan'}</Text>
          <View style={{ width: 60 }} />
        </View>

        <ScrollView contentContainerStyle={styles.formContainer}>
          <Text style={styles.formLabel}>Plan Name *</Text>
          <TextInput
            style={styles.formInput}
            placeholder="e.g. User Authentication Suite"
            placeholderTextColor={colors.slate[400]}
            value={formName}
            onChangeText={setFormName}
          />

          <Text style={styles.formLabel}>Target Website URL *</Text>
          <TextInput
            style={styles.formInput}
            placeholder="e.g. https://my-app.com/login"
            placeholderTextColor={colors.slate[400]}
            value={formUrl}
            onChangeText={setFormUrl}
            autoCapitalize="none"
            keyboardType="url"
          />

          <Text style={styles.formLabel}>Verification Criteria (One instruction per line) *</Text>
          <TextInput
            style={[styles.formInput, styles.formTextArea]}
            placeholder="e.g.&#10;1. Element visible: #username-input&#10;2. Element visible: #password-input&#10;3. Page loads successfully"
            placeholderTextColor={colors.slate[400]}
            value={formCriteria}
            onChangeText={setFormCriteria}
            multiline
            numberOfLines={5}
          />

          <Text style={styles.formLabel}>Execution Schedule</Text>
          <View style={styles.scheduleRow}>
            {(['manual', 'daily', 'weekly'] as const).map((sched) => (
              <TouchableOpacity
                key={sched}
                style={[styles.scheduleOption, formSchedule === sched && styles.activeScheduleOption]}
                onPress={() => setFormSchedule(sched)}
              >
                <Text style={[styles.scheduleOptionText, formSchedule === sched && styles.activeScheduleOptionText]}>
                  {sched.toUpperCase()}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          <TouchableOpacity 
            style={[styles.submitPlanButton, submittingPlan && styles.disabledButton]} 
            onPress={handleCreateOrEditPlan}
            disabled={submittingPlan}
          >
            {submittingPlan ? (
              <ActivityIndicator color={colors.white} />
            ) : (
              <Text style={styles.submitPlanButtonText}>Save Test Plan</Text>
            )}
          </TouchableOpacity>
        </ScrollView>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Testing Dashboard</Text>
        {activeTab === 'plans' && (
          <TouchableOpacity style={styles.addPlanButton} onPress={() => {
            setEditingPlan(null);
            setFormName('');
            setFormUrl('');
            setFormCriteria('');
            setFormSchedule('manual');
            setShowPlanForm(true);
          }}>
            <Text style={styles.addPlanButtonText}>+ Plan</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Tabs */}
      <View style={styles.tabsContainer}>
        {(['plans', 'runs', 'subscription'] as const).map((tab) => (
          <TouchableOpacity
            key={tab}
            style={[styles.tabButton, activeTab === tab && styles.activeTabButton]}
            onPress={() => setActiveTab(tab)}
          >
            <Text style={[styles.tabButtonText, activeTab === tab && styles.activeTabButtonText]}>
              {tab === 'subscription' ? 'Billing' : tab.charAt(0).toUpperCase() + tab.slice(1)}
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
      ) : activeTab === 'plans' ? (
        <FlatList
          data={plans}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          renderItem={renderPlanItem}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>No SaaS testing plans configured</Text>
            </View>
          }
        />
      ) : activeTab === 'runs' ? (
        <FlatList
          data={runs}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          renderItem={renderRunItem}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>No test runs yet</Text>
            </View>
          }
        />
      ) : (
        <ScrollView contentContainerStyle={styles.billingContainer}>
          <View style={styles.subscriptionCard}>
            <Text style={styles.subLabel}>Current SaaS Testing Tier</Text>
            <Text style={styles.subTier}>{subscription?.tier ? subscription.tier.toUpperCase() : 'FREE MOCK'}</Text>
            
            <View style={styles.meterContainer}>
              <View style={styles.meterLabelRow}>
                <Text style={styles.meterLabel}>Monthly Run Usage</Text>
                <Text style={styles.meterValue}>
                  {subscription?.runs_used || 0} / {subscription?.runs_limit || 5}
                </Text>
              </View>
              <View style={styles.progressBarBg}>
                <View style={[
                  styles.progressBarFill, 
                  { width: `${Math.min(100, (((subscription?.runs_used || 0) / (subscription?.runs_limit || 5)) * 100))}%` }
                ]} />
              </View>
            </View>

            <Text style={styles.subStatus}>
              Status: {subscription?.is_active ? 'ACTIVE' : 'INACTIVE'}
            </Text>
          </View>

          <Text style={styles.tierSectionTitle}>Available Upgrade Tiers</Text>

          {/* Pricing cards */}
          <View style={styles.tierPricingCard}>
            <View style={styles.tierHeader}>
              <Text style={styles.tierName}>Basic Tier</Text>
              <Text style={styles.tierPrice}>$50/mo</Text>
            </View>
            <Text style={styles.tierDescription}>
              For individual projects needing routine verification checks.
            </Text>
            <Text style={styles.tierFeature}>• Up to 3 Test Plans</Text>
            <Text style={styles.tierFeature}>• 50 Monthly Runs</Text>
            <Text style={styles.tierFeature}>• Automatic Daily/Weekly Schedules</Text>
            <TouchableOpacity 
              style={[styles.subscribeBtn, subscription?.tier?.toLowerCase() === 'basic' && styles.disabledButton]} 
              onPress={() => handleSubscribe('basic')}
              disabled={subscription?.tier?.toLowerCase() === 'basic'}
            >
              <Text style={styles.subscribeBtnText}>
                {subscription?.tier?.toLowerCase() === 'basic' ? 'Current Tier' : 'Upgrade to Basic'}
              </Text>
            </TouchableOpacity>
          </View>

          <View style={[styles.tierPricingCard, styles.proPricingCard]}>
            <View style={styles.tierHeader}>
              <Text style={[styles.tierName, styles.proColor]}>Pro Tier</Text>
              <Text style={[styles.tierPrice, styles.proColor]}>$200/mo</Text>
            </View>
            <Text style={styles.tierDescription}>
              For developer teams needing production grade agentic verification.
            </Text>
            <Text style={styles.tierFeature}>• Up to 20 Test Plans</Text>
            <Text style={styles.tierFeature}>• 500 Monthly Runs</Text>
            <Text style={styles.tierFeature}>• Automatic Schedules + CI/CD Integration</Text>
            <TouchableOpacity 
              style={[styles.subscribeBtn, styles.proSubscribeBtn, subscription?.tier?.toLowerCase() === 'pro' && styles.disabledButton]} 
              onPress={() => handleSubscribe('pro')}
              disabled={subscription?.tier?.toLowerCase() === 'pro'}
            >
              <Text style={styles.proSubscribeBtnText}>
                {subscription?.tier?.toLowerCase() === 'pro' ? 'Current Tier' : 'Upgrade to Pro'}
              </Text>
            </TouchableOpacity>
          </View>
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
  addPlanButton: {
    backgroundColor: colors.indigo[600],
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  addPlanButtonText: {
    color: colors.white,
    fontSize: fontSize.xs,
    fontWeight: '700',
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
  card: {
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
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  cardTitle: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.slate[900],
    flex: 1,
  },
  cardUrl: {
    fontSize: fontSize.xs,
    color: colors.indigo[600],
    marginBottom: spacing.sm,
  },
  cardMeta: {
    fontSize: fontSize.xs,
    color: colors.slate[500],
    marginBottom: 2,
  },
  statusBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.full,
  },
  statusActive: {
    backgroundColor: colors.emerald[100],
  },
  statusInactive: {
    backgroundColor: colors.slate[100],
  },
  statusFailed: {
    backgroundColor: colors.red[100],
  },
  statusRunning: {
    backgroundColor: colors.indigo[100],
  },
  statusText: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    color: colors.slate[700],
  },
  actionRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    marginTop: spacing.md,
  },
  actionButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.slate[300],
    marginLeft: spacing.sm,
  },
  actionButtonText: {
    fontSize: fontSize.xs,
    color: colors.slate[600],
    fontWeight: '600',
  },
  triggerButton: {
    backgroundColor: colors.indigo[600],
    borderColor: colors.indigo[600],
  },
  triggerButtonText: {
    fontSize: fontSize.xs,
    color: colors.white,
    fontWeight: '700',
  },
  statsRow: {
    flexDirection: 'row',
    marginBottom: spacing.sm,
  },
  statText: {
    fontSize: fontSize.xs,
    color: colors.slate[600],
    marginRight: spacing.md,
    fontWeight: '600',
  },
  statFailed: {
    color: colors.red[600],
  },
  billingContainer: {
    padding: spacing.lg,
  },
  subscriptionCard: {
    backgroundColor: colors.slate[900],
    borderRadius: borderRadius.xl,
    padding: spacing.xl,
    marginBottom: spacing.xl,
  },
  subLabel: {
    color: colors.slate[400],
    fontSize: fontSize.xs,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  subTier: {
    color: colors.white,
    fontSize: fontSize.xl,
    fontWeight: '800',
    marginTop: spacing.xs,
    marginBottom: spacing.md,
  },
  meterContainer: {
    marginVertical: spacing.md,
  },
  meterLabelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.xs,
  },
  meterLabel: {
    color: colors.slate[300],
    fontSize: fontSize.xs,
  },
  meterValue: {
    color: colors.white,
    fontSize: fontSize.xs,
    fontWeight: '700',
  },
  progressBarBg: {
    height: 8,
    backgroundColor: colors.slate[700],
    borderRadius: borderRadius.full,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: colors.indigo[500],
  },
  subStatus: {
    color: colors.emerald[400],
    fontSize: fontSize.xs,
    fontWeight: '600',
    marginTop: spacing.sm,
  },
  tierSectionTitle: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.slate[900],
    marginBottom: spacing.md,
  },
  tierPricingCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.slate[200],
  },
  proPricingCard: {
    borderColor: colors.indigo[500],
    borderWidth: 2,
  },
  tierHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  tierName: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.slate[900],
  },
  proColor: {
    color: colors.indigo[600],
  },
  tierPrice: {
    fontSize: fontSize.md,
    fontWeight: '800',
    color: colors.slate[900],
  },
  tierDescription: {
    fontSize: fontSize.sm,
    color: colors.slate[600],
    marginBottom: spacing.md,
    lineHeight: 18,
  },
  tierFeature: {
    fontSize: fontSize.xs,
    color: colors.slate[700],
    marginBottom: 4,
  },
  subscribeBtn: {
    backgroundColor: colors.slate[100],
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
    alignItems: 'center',
    marginTop: spacing.lg,
  },
  proSubscribeBtn: {
    backgroundColor: colors.indigo[600],
  },
  subscribeBtnText: {
    color: colors.slate[800],
    fontSize: fontSize.xs,
    fontWeight: '700',
  },
  proSubscribeBtnText: {
    color: colors.white,
    fontSize: fontSize.xs,
    fontWeight: '700',
  },
  detailScroll: {
    padding: spacing.lg,
    backgroundColor: colors.white,
  },
  statusBanner: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.md,
    marginBottom: spacing.lg,
    alignItems: 'center',
  },
  bannerPassed: {
    backgroundColor: colors.emerald[100],
  },
  bannerFailed: {
    backgroundColor: colors.red[100],
  },
  bannerRunning: {
    backgroundColor: colors.indigo[100],
  },
  bannerText: {
    fontSize: fontSize.sm,
    fontWeight: '700',
    color: colors.slate[800],
  },
  detailTitle: {
    fontSize: fontSize.lg,
    fontWeight: '800',
    color: colors.slate[900],
    marginBottom: spacing.xs,
  },
  detailUrl: {
    fontSize: fontSize.xs,
    color: colors.indigo[600],
    marginBottom: spacing.md,
  },
  divider: {
    height: 1,
    backgroundColor: colors.slate[200],
    marginVertical: spacing.md,
  },
  errorContainer: {
    backgroundColor: colors.red[50],
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.lg,
    borderWidth: 1,
    borderColor: colors.red[100],
  },
  errorTitle: {
    fontSize: fontSize.xs,
    fontWeight: '700',
    color: colors.red[700],
    marginBottom: 4,
    textTransform: 'uppercase',
  },
  errorBody: {
    fontSize: fontSize.xs,
    color: colors.red[600],
    lineHeight: 16,
  },
  sectionTitle: {
    fontSize: fontSize.sm,
    fontWeight: '700',
    color: colors.slate[900],
    marginBottom: spacing.sm,
    textTransform: 'uppercase',
  },
  stepCard: {
    backgroundColor: colors.slate[50],
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.slate[200],
  },
  stepHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  stepNumber: {
    fontSize: fontSize.xs,
    fontWeight: '700',
    color: colors.slate[500],
  },
  miniBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 1,
    borderRadius: borderRadius.full,
  },
  miniPassed: {
    backgroundColor: colors.emerald[100],
  },
  miniFailed: {
    backgroundColor: colors.red[100],
  },
  miniText: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.slate[700],
  },
  stepCriterion: {
    fontSize: fontSize.sm,
    color: colors.slate[800],
    fontWeight: '500',
  },
  stepError: {
    fontSize: fontSize.xs,
    color: colors.red[600],
    marginTop: 4,
    fontStyle: 'italic',
  },
  screenshotsScroll: {
    flexDirection: 'row',
  },
  screenshotWrapper: {
    marginRight: spacing.md,
    borderWidth: 1,
    borderColor: colors.slate[200],
    borderRadius: borderRadius.md,
    overflow: 'hidden',
    backgroundColor: colors.slate[100],
  },
  screenshot: {
    width: 250,
    height: 150,
  },
  formContainer: {
    padding: spacing.lg,
    backgroundColor: colors.white,
  },
  formLabel: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.slate[800],
    marginBottom: spacing.xs,
  },
  formInput: {
    backgroundColor: colors.slate[50],
    borderWidth: 1,
    borderColor: colors.slate[200],
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: fontSize.sm,
    color: colors.slate[900],
    marginBottom: spacing.lg,
  },
  formTextArea: {
    height: 100,
    textAlignVertical: 'top',
  },
  scheduleRow: {
    flexDirection: 'row',
    marginBottom: spacing.xl,
  },
  scheduleOption: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.slate[200],
    borderRadius: borderRadius.md,
    paddingVertical: spacing.sm,
    alignItems: 'center',
    marginRight: spacing.sm,
    backgroundColor: colors.slate[50],
  },
  activeScheduleOption: {
    borderColor: colors.indigo[500],
    backgroundColor: colors.indigo[50],
  },
  scheduleOptionText: {
    fontSize: fontSize.xs,
    fontWeight: '700',
    color: colors.slate[600],
  },
  activeScheduleOptionText: {
    color: colors.indigo[700],
  },
  submitPlanButton: {
    backgroundColor: colors.indigo[600],
    borderRadius: borderRadius.lg,
    paddingVertical: spacing.md,
    alignItems: 'center',
    marginTop: spacing.md,
    marginBottom: spacing.xl,
  },
  submitPlanButtonText: {
    color: colors.white,
    fontSize: fontSize.md,
    fontWeight: '700',
  },
  disabledButton: {
    backgroundColor: colors.slate[300],
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

export default TestingScreen;
