import React, { useState, useEffect } from 'react'
import {
  X,
  Plus,
  Search,
  FlaskConical,
  Activity,
  CreditCard,
  Play,
  Calendar,
  CheckCircle,
  XCircle,
  ExternalLink,
  ChevronRight,
  TrendingUp,
  AlertCircle,
  Loader2,
  Clock,
  Layers,
  Edit2
} from 'lucide-react'
import { useTestingStore, TestPlan, TestRun } from '../stores/testing'
import { TestRunDetail } from './TestRunDetail'

interface TestingDashboardProps {
  onClose: () => void
}

type TabType = 'plans' | 'runs' | 'subscription'

export const TestingDashboard: React.FC<TestingDashboardProps> = ({ onClose }) => {
  const {
    plans,
    runs,
    activeRun,
    subscription,
    isLoading,
    isProcessing,
    error,
    fetchPlans,
    createPlan,
    triggerRun,
    fetchRuns,
    fetchRunDetail,
    fetchSubscription
  } = useTestingStore()

  const [activeTab, setActiveTab] = useState<TabType>('plans')
  const [searchTerm, setSearchTerm] = useState('')
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null)

  // Plan Modal Form State
  const [isPlanModalOpen, setIsPlanModalOpen] = useState(false)
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create')
  const [editingPlanId, setEditingPlanId] = useState<string | null>(null)
  const [urlInput, setUrlInput] = useState('')
  const [criteriaInput, setCriteriaInput] = useState('')
  const [scheduleInput, setScheduleInput] = useState<'daily' | 'hourly' | 'on-demand'>('on-demand')

  useEffect(() => {
    fetchPlans()
    fetchRuns()
    fetchSubscription()
  }, [])

  // Refetch when switching tabs to ensure freshness
  useEffect(() => {
    if (activeTab === 'plans') fetchPlans()
    if (activeTab === 'runs') fetchRuns()
    if (activeTab === 'subscription') fetchSubscription()
  }, [activeTab])

  const handleOpenCreateModal = () => {
    setFormMode('create')
    setEditingPlanId(null)
    setUrlInput('')
    setCriteriaInput('')
    setScheduleInput('on-demand')
    setIsPlanModalOpen(true)
  }

  const handleOpenEditModal = (plan: TestPlan) => {
    setFormMode('edit')
    setEditingPlanId(plan.id)
    setUrlInput(plan.url)
    setCriteriaInput(plan.criteria)
    setScheduleInput(plan.schedule)
    setIsPlanModalOpen(true)
  }

  const handlePlanSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!urlInput.trim() || !criteriaInput.trim()) {
      alert('Please fill out all required fields!')
      return
    }

    // Basic URL validation
    let validatedUrl = urlInput.trim()
    if (!/^https?:\/\//i.test(validatedUrl)) {
      validatedUrl = `https://${validatedUrl}`
    }

    const payload: any = {
      url: validatedUrl,
      criteria: criteriaInput.trim(),
      schedule: scheduleInput
    }

    if (formMode === 'edit' && editingPlanId) {
      payload.id = editingPlanId
    }

    const res = await createPlan(payload)
    if (res) {
      setIsPlanModalOpen(false)
      // Reset
      setUrlInput('')
      setCriteriaInput('')
      setScheduleInput('on-demand')
      fetchPlans()
    }
  }

  const handleTriggerTest = async (planId: string) => {
    const run = await triggerRun(planId)
    if (run) {
      // Automatically navigate and expand the detailed run result
      setActiveTab('runs')
      setExpandedRunId(run.id)
      fetchRunDetail(run.id)
    }
  }

  const handleExpandRun = (runId: string) => {
    if (expandedRunId === runId) {
      setExpandedRunId(null)
    } else {
      setExpandedRunId(runId)
      fetchRunDetail(runId)
    }
  }

  const handleUpgradeTier = () => {
    if (subscription?.stripe_payment_link) {
      // @ts-ignore
      if (window.api && typeof window.api.openExternal === 'function') {
        // @ts-ignore
        window.api.openExternal(subscription.stripe_payment_link)
      } else {
        window.open(subscription.stripe_payment_link, '_blank')
      }
    } else {
      alert('Stripe integration is being wired up by our Backend Engineer. Stay tuned!')
    }
  }

  const formatDate = (isoStr?: string | null) => {
    if (!isoStr) return 'Never'
    try {
      return new Date(isoStr).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    } catch {
      return isoStr
    }
  }

  const getStatusStyle = (status: string) => {
    switch (status) {
      case 'active':
      case 'passed':
        return 'bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20'
      case 'failed':
        return 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20'
      case 'running':
        return 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20 animate-pulse'
      case 'queued':
        return 'bg-slate-100 text-slate-600 border-slate-200'
      case 'inactive':
      default:
        return 'bg-slate-100 dark:bg-slate-850 text-slate-500 border-slate-200 dark:border-slate-800'
    }
  }

  // Filter plans based on search
  const filteredPlans = plans.filter(
    (p) =>
      p.url.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.criteria.toLowerCase().includes(searchTerm.toLowerCase())
  )

  // Filter runs based on search
  const filteredRuns = runs.filter(
    (r) =>
      r.plan_url?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.status.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const progressPercentage = subscription
    ? Math.min((subscription.runs_used / subscription.runs_limit) * 100, 100)
    : 0

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fadeIn">
      <div className="w-full max-w-5xl h-[85vh] bg-white dark:bg-slate-900 rounded-2xl shadow-2xl overflow-hidden flex flex-col border border-slate-200 dark:border-slate-800">
        
        {/* Top Header */}
        <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-950/20">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-xl border border-indigo-500/20">
              <FlaskConical size={22} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-white">Jarvis Automated Testing Service</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1">
                <span>Run automated visual and functional QA test runs on any live website</span>
                {subscription && (
                  <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                    ({subscription.tier} Tier)
                  </span>
                )}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Navigation Tabs Bar */}
        <div className="px-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/30 dark:bg-slate-950/10">
          <div className="flex gap-1 py-2">
            <button
              onClick={() => {
                setActiveTab('plans')
                setExpandedRunId(null)
              }}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'plans'
                  ? 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 border border-indigo-100 dark:border-indigo-900/50'
                  : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-850/50'
              }`}
            >
              <Layers size={15} />
              Test Plans
              <span className="text-xs font-bold px-1.5 py-0.2 bg-slate-100 dark:bg-slate-800 rounded text-slate-500">
                {plans.length}
              </span>
            </button>
            <button
              onClick={() => setActiveTab('runs')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'runs'
                  ? 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 border border-indigo-100 dark:border-indigo-900/50'
                  : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-850/50'
              }`}
            >
              <Activity size={15} />
              Test Runs
              <span className="text-xs font-bold px-1.5 py-0.2 bg-slate-100 dark:bg-slate-800 rounded text-slate-500">
                {runs.length}
              </span>
            </button>
            <button
              onClick={() => {
                setActiveTab('subscription')
                setExpandedRunId(null)
              }}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'subscription'
                  ? 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 border border-indigo-100 dark:border-indigo-900/50'
                  : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-850/50'
              }`}
            >
              <CreditCard size={15} />
              Subscription & Usage
            </button>
          </div>

          {/* Inline Action Buttons */}
          <div className="flex items-center gap-3">
            {activeTab === 'plans' && (
              <button
                onClick={handleOpenCreateModal}
                className="flex items-center gap-1.5 px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold shadow-sm hover:shadow transition-all"
              >
                <Plus size={15} />
                Create Test Plan
              </button>
            )}
            {activeTab !== 'subscription' && (
              <div className="relative w-48 md:w-64">
                <Search size={14} className="absolute left-3 top-2.5 text-slate-400 dark:text-slate-500" />
                <input
                  type="text"
                  placeholder={activeTab === 'plans' ? 'Search plans...' : 'Search runs...'}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 border border-slate-200 dark:border-slate-800 rounded-lg text-xs bg-slate-50/50 dark:bg-slate-950/20 focus:outline-none focus:border-indigo-500 text-slate-850 dark:text-white"
                />
              </div>
            )}
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 overflow-y-auto min-h-0 relative">
          
          {isLoading && !isProcessing && (
            <div className="absolute inset-0 bg-white/70 dark:bg-slate-900/70 z-10 flex items-center justify-center">
              <div className="flex flex-col items-center gap-2">
                <Loader2 className="animate-spin text-indigo-600 w-8 h-8" />
                <p className="text-sm font-medium text-slate-500">Loading dynamic data...</p>
              </div>
            </div>
          )}

          {error && (
            <div className="p-4 mx-6 my-4 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/40 text-red-600 dark:text-red-400 rounded-xl flex items-center gap-3 text-sm">
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}

          {/* Tab 1: Test Plans View */}
          {activeTab === 'plans' && (
            <div className="p-6">
              {filteredPlans.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {filteredPlans.map((plan) => (
                    <div
                      key={plan.id}
                      className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm hover:shadow-md transition-all flex flex-col justify-between"
                    >
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${getStatusStyle(plan.status)}`}>
                            {plan.status.toUpperCase()}
                          </span>
                          <span className="text-[10px] font-bold text-indigo-500 bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-100 dark:border-indigo-900/50 px-2 py-0.5 rounded uppercase tracking-wider">
                            {plan.schedule}
                          </span>
                        </div>

                        <div>
                          <h4 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-1 truncate" title={plan.url}>
                            {plan.url}
                            <a
                              href={plan.url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-slate-400 hover:text-indigo-500 transition-colors"
                            >
                              <ExternalLink size={13} />
                            </a>
                          </h4>
                          <p className="text-xs text-slate-400 font-mono mt-1">
                            Plan ID: {plan.id.slice(0, 8)}
                          </p>
                        </div>

                        <div className="pt-2">
                          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                            Test Assertions Summary:
                          </p>
                          <div className="bg-slate-50 dark:bg-slate-950/40 p-3 rounded-xl border border-slate-100 dark:border-slate-850 text-xs text-slate-600 dark:text-slate-400 h-24 overflow-y-auto whitespace-pre-line leading-relaxed font-mono">
                            {plan.criteria}
                          </div>
                        </div>
                      </div>

                      <div className="border-t border-slate-100 dark:border-slate-850 pt-4 mt-4 flex items-center justify-between text-xs text-slate-500">
                        <div className="space-y-1">
                          <p>Last Run: <span className="font-medium text-slate-700 dark:text-slate-300">{formatDate(plan.last_run_at)}</span></p>
                          {plan.pass_rate !== null && plan.pass_rate !== undefined && (
                            <p className="flex items-center gap-1">
                              Pass Rate: 
                              <span className={`font-bold px-1.5 py-0.2 rounded ${
                                plan.pass_rate >= 90
                                  ? 'bg-green-500/10 text-green-600'
                                  : plan.pass_rate >= 70
                                  ? 'bg-amber-500/10 text-amber-600'
                                  : 'bg-red-500/10 text-red-600'
                              }`}>
                                {plan.pass_rate}%
                              </span>
                            </p>
                          )}
                        </div>

                        <div className="flex gap-1.5">
                          <button
                            onClick={() => handleOpenEditModal(plan)}
                            className="p-2 border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 rounded-lg transition-colors"
                            title="Edit test plan parameters"
                          >
                            <Edit2 size={14} />
                          </button>
                          <button
                            onClick={() => handleTriggerTest(plan.id)}
                            disabled={isProcessing}
                            className="flex items-center gap-1 px-3 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 disabled:dark:bg-slate-800 text-white rounded-lg font-semibold shadow-sm hover:shadow transition-all"
                          >
                            <Play size={12} className="fill-current" />
                            Run Plan
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-24 flex flex-col items-center justify-center bg-white dark:bg-slate-900 border border-dashed border-slate-200 dark:border-slate-800 rounded-2xl">
                  <FlaskConical size={48} className="text-slate-300 dark:text-slate-700 mb-3" />
                  <h3 className="text-lg font-bold text-slate-800 dark:text-slate-200">No QA Test Plans Found</h3>
                  <p className="text-sm text-slate-500 max-w-sm mt-1 mb-4">
                    Create a test plan containing specific visual or procedural criteria to start running QA automation runs.
                  </p>
                  <button
                    onClick={handleOpenCreateModal}
                    className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold shadow"
                  >
                    <Plus size={16} />
                    Create Your First Test Plan
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Tab 2: Test Runs List / Expand View */}
          {activeTab === 'runs' && (
            <div className="h-full">
              {expandedRunId && activeRun ? (
                // Detailed run output viewer
                <div className="h-full">
                  <TestRunDetail
                    run={activeRun}
                    onClose={() => setExpandedRunId(null)}
                    onTriggerPlan={handleTriggerTest}
                    isTriggering={isProcessing}
                  />
                </div>
              ) : (
                // Test runs list
                <div className="p-6">
                  {filteredRuns.length > 0 ? (
                    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm">
                      <table className="w-full text-left border-collapse">
                        <thead>
                          <tr className="bg-slate-50 dark:bg-slate-950/40 border-b border-slate-200 dark:border-slate-800 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                            <th className="py-3 px-5">Test Run ID</th>
                            <th className="py-3 px-5">Target URL</th>
                            <th className="py-3 px-5">Outcome</th>
                            <th className="py-3 px-5">Assertions (P/F)</th>
                            <th className="py-3 px-5">Duration</th>
                            <th className="py-3 px-5">Executed At</th>
                            <th className="py-3 px-5 text-right">Action</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 dark:divide-slate-850 text-sm text-slate-700 dark:text-slate-300">
                          {filteredRuns.map((run) => (
                            <tr
                              key={run.id}
                              onClick={() => handleExpandRun(run.id)}
                              className="hover:bg-slate-50/50 dark:hover:bg-slate-950/20 cursor-pointer transition-colors"
                            >
                              <td className="py-4 px-5 font-mono text-xs text-indigo-600 dark:text-indigo-400 font-semibold">
                                #{run.id.slice(-6).toUpperCase()}
                              </td>
                              <td className="py-4 px-5 font-medium max-w-xs truncate" title={run.plan_url}>
                                {run.plan_url}
                              </td>
                              <td className="py-4 px-5">
                                <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border uppercase tracking-wider ${getStatusStyle(run.status)}`}>
                                  {run.status}
                                </span>
                              </td>
                              <td className="py-4 px-5">
                                <span className="text-xs font-medium text-green-500">
                                  {run.passed_count} passed
                                </span>
                                {run.failed_count > 0 && (
                                  <span className="text-xs font-medium text-red-500 ml-2">
                                    {run.failed_count} failed
                                  </span>
                                )}
                              </td>
                              <td className="py-4 px-5 font-mono text-xs flex items-center gap-1">
                                <Clock size={12} className="text-slate-400" />
                                {run.duration}s
                              </td>
                              <td className="py-4 px-5 text-xs text-slate-500">
                                {formatDate(run.created_at)}
                              </td>
                              <td className="py-4 px-5 text-right">
                                <button className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg text-slate-400 hover:text-indigo-500 transition-colors">
                                  <ChevronRight size={16} />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-center py-24 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl">
                      <Activity size={48} className="text-slate-300 dark:text-slate-700 mb-3" />
                      <h3 className="text-lg font-bold text-slate-850 dark:text-white">No QA Runs Recorded</h3>
                      <p className="text-sm text-slate-500 max-w-sm mx-auto mt-1">
                        Trigger a test execution against any of your test plans to see the diagnostic results, assertion logs, and screenshot gallery.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Tab 3: Subscription Management */}
          {activeTab === 'subscription' && subscription && (
            <div className="p-8 max-w-3xl mx-auto space-y-8">
              
              {/* Main Subscription details card */}
              <div className="bg-slate-50 dark:bg-slate-950/40 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 md:p-8 grid grid-cols-1 md:grid-cols-3 gap-6 items-center shadow-sm">
                <div className="md:col-span-2 space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-extrabold px-2.5 py-0.5 bg-indigo-600 text-white rounded-full uppercase tracking-wider">
                      Current Tier
                    </span>
                    <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                      Automated Testing SaaS
                    </span>
                  </div>
                  <h3 className="text-3xl font-extrabold text-slate-950 dark:text-white flex items-baseline gap-1.5">
                    {subscription.tier} Plan
                    <span className="text-sm font-normal text-slate-500">
                      {subscription.tier === 'Basic' ? '$50/month' : '$200/month'}
                    </span>
                  </h3>
                  <p className="text-sm text-slate-500 leading-relaxed">
                    Provides headless Chrome browser automation workers to periodically scrape, click, capture screenshots, and audit visual changes on your specified staging or production sites.
                  </p>
                </div>

                <div className="flex flex-col items-center md:items-end justify-center p-4 bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800/80 rounded-2xl shadow-sm">
                  <span className="text-xs text-slate-400 font-medium mb-1">Status</span>
                  <div className="flex items-center gap-1.5 text-green-500 font-bold text-sm mb-3">
                    <CheckCircle size={16} />
                    Active Subscription
                  </div>
                  <button
                    onClick={handleUpgradeTier}
                    className="w-full px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-semibold text-center transition-all shadow hover:shadow-md"
                  >
                    {subscription.tier === 'Basic' ? 'Upgrade to Pro' : 'Manage on Stripe'}
                  </button>
                </div>
              </div>

              {/* Usage Progress Tracker bar */}
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 space-y-4 shadow-sm">
                <div className="flex justify-between items-end">
                  <div className="space-y-1">
                    <h4 className="text-sm font-bold text-slate-800 dark:text-white">Monthly QA Browser Run Limit</h4>
                    <p className="text-xs text-slate-500">Resets automatically at the end of your billing cycle.</p>
                  </div>
                  <span className="text-sm font-mono font-bold text-slate-900 dark:text-white bg-slate-50 dark:bg-slate-850 px-3 py-1 rounded-lg">
                    {subscription.runs_used} / {subscription.runs_limit} runs
                  </span>
                </div>

                <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-3 overflow-hidden">
                  <div
                    className="bg-indigo-600 h-full transition-all duration-500 rounded-full"
                    style={{ width: `${progressPercentage}%` }}
                  ></div>
                </div>

                <div className="flex justify-between text-xs text-slate-400">
                  <span>0% used</span>
                  <span>{progressPercentage.toFixed(0)}% limit consumed</span>
                  <span>100% full</span>
                </div>
              </div>

              {/* Tiers Pricing Grid Comparison */}
              <div className="space-y-4 pt-4">
                <h4 className="text-sm font-bold text-slate-800 dark:text-white uppercase tracking-wider flex items-center gap-1.5">
                  <TrendingUp size={15} className="text-indigo-500" /> Comparison of Plan Tiers
                </h4>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Basic Card */}
                  <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 space-y-4">
                    <div className="flex justify-between items-start">
                      <div>
                        <h5 className="text-base font-bold text-slate-900 dark:text-white">Basic QA Tier</h5>
                        <p className="text-xs text-slate-400">Ideal for small startups & single landing pages</p>
                      </div>
                      <span className="text-sm font-bold px-2.5 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 rounded-md">$50/mo</span>
                    </div>
                    
                    <ul className="space-y-2.5 text-xs text-slate-600 dark:text-slate-400">
                      <li className="flex items-center gap-2">
                        <CheckCircle size={14} className="text-green-500 flex-shrink-0" />
                        <span>Up to 20 automated test runs per month</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <CheckCircle size={14} className="text-green-500 flex-shrink-0" />
                        <span>Daily schedule runner capability</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <CheckCircle size={14} className="text-green-500 flex-shrink-0" />
                        <span>Up to 5 execution steps/plan</span>
                      </li>
                      <li className="flex items-center gap-2 text-slate-350 dark:text-slate-600">
                        <XCircle size={14} className="text-slate-300 dark:text-slate-700 flex-shrink-0" />
                        <span>No hourly scheduling (Pro feature)</span>
                      </li>
                    </ul>
                  </div>

                  {/* Pro Card */}
                  <div className="bg-white dark:bg-slate-900 border border-indigo-500/30 dark:border-indigo-500/20 rounded-2xl p-5 space-y-4 ring-2 ring-indigo-500/10">
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="flex items-center gap-1.5">
                          <h5 className="text-base font-bold text-slate-900 dark:text-white">Pro Enterprise Tier</h5>
                          <span className="text-[9px] font-extrabold bg-indigo-100 text-indigo-700 dark:bg-indigo-900/35 dark:text-indigo-400 px-1.5 py-0.2 rounded uppercase">Best Value</span>
                        </div>
                        <p className="text-xs text-slate-400">Perfect for multi-page applications & heavy QA</p>
                      </div>
                      <span className="text-sm font-bold px-2.5 py-0.5 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 rounded-md">$200/mo</span>
                    </div>
                    
                    <ul className="space-y-2.5 text-xs text-slate-600 dark:text-slate-400 font-medium">
                      <li className="flex items-center gap-2">
                        <CheckCircle size={14} className="text-green-500 flex-shrink-0" />
                        <span>Up to 100 automated test runs per month</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <CheckCircle size={14} className="text-green-500 flex-shrink-0" />
                        <span>Hourly & Daily background scheduler workers</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <CheckCircle size={14} className="text-green-500 flex-shrink-0" />
                        <span>Unlimited test execution steps & assertions</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <CheckCircle size={14} className="text-green-500 flex-shrink-0" />
                        <span>Visual regression diff highlight overlays</span>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          )}

        </div>
      </div>

      {/* CREATE/EDIT PLAN FORM MODAL */}
      {isPlanModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4 animate-fadeIn">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-2xl shadow-xl overflow-hidden border border-slate-200 dark:border-slate-800">
            
            {/* Modal Header */}
            <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-950/20">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                {formMode === 'create' ? 'Create Automated QA Test Plan' : 'Edit Test Plan Configuration'}
              </h3>
              <button
                onClick={() => setIsPlanModalOpen(false)}
                className="p-1 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg text-slate-400 hover:text-slate-600 transition-colors"
              >
                <X size={16} />
              </button>
            </div>

            {/* Modal Form */}
            <form onSubmit={handlePlanSubmit} className="p-5 space-y-4">
              {/* URL Input */}
              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Target Website URL <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. staging.myshopifyapp.com"
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 dark:border-slate-800 rounded-lg text-sm bg-slate-50/50 dark:bg-slate-950/20 focus:outline-none focus:border-indigo-500 text-slate-850 dark:text-white font-medium"
                />
              </div>

              {/* Criteria Input */}
              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider flex justify-between">
                  <span>Execution Steps / Test Criteria</span>
                  <span className="text-[10px] font-normal text-slate-400">One item per line</span>
                </label>
                <textarea
                  required
                  rows={4}
                  placeholder="e.g.&#10;1. Open homepage and verify title contains 'Shop'&#10;2. Click element containing 'Featured Product'&#10;3. Assert visual comparison of cart page&#10;4. Fill form 'Email' with 'qa@test.com'"
                  value={criteriaInput}
                  onChange={(e) => setCriteriaInput(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 dark:border-slate-800 rounded-lg text-sm bg-slate-50/50 dark:bg-slate-950/20 focus:outline-none focus:border-indigo-500 text-slate-850 dark:text-white font-mono leading-relaxed"
                ></textarea>
              </div>

              {/* Schedule Select */}
              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Background Runner Schedule
                </label>
                <select
                  value={scheduleInput}
                  onChange={(e: any) => setScheduleInput(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 dark:border-slate-800 rounded-lg text-sm bg-slate-50/50 dark:bg-slate-950/20 focus:outline-none focus:border-indigo-500 text-slate-850 dark:text-white font-semibold"
                >
                  <option value="on-demand">On-Demand Only (Manual runs)</option>
                  <option value="daily">Daily Cron Runner</option>
                  <option value="hourly">Hourly Cron Runner (Pro Tier only)</option>
                </select>
              </div>

              {/* Form Buttons */}
              <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsPlanModalOpen(false)}
                  className="px-4 py-2 border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 rounded-lg text-xs font-bold text-slate-600 dark:text-slate-400 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isProcessing}
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white rounded-lg text-xs font-bold shadow hover:shadow-md transition-all flex items-center gap-1"
                >
                  {isProcessing ? 'Saving...' : 'Save Configuration'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
