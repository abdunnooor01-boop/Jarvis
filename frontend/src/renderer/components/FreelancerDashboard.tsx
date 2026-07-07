import React, { useState, useEffect } from 'react'
import {
  X,
  Search,
  DollarSign,
  Clock,
  Sparkles,
  FileText,
  Download,
  AlertCircle,
  CheckCircle,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Inbox,
  CreditCard,
  Plus
} from 'lucide-react'
import { useFreelanceStore, TaskTemplate, FreelanceJob } from '../stores/freelance'

interface FreelancerDashboardProps {
  onClose: () => void
}

type TabType = 'available' | 'jobs'

export const FreelancerDashboard: React.FC<FreelancerDashboardProps> = ({ onClose }) => {
  const {
    templates,
    jobs,
    isProcessing,
    isLoading,
    error,
    earnings,
    fetchTemplates,
    createOrder,
    fetchJobs
  } = useFreelanceStore()

  const [activeTab, setActiveTab] = useState<TabType>('available')
  const [selectedTemplate, setSelectedTemplate] = useState<TaskTemplate | null>(null)
  
  // Submission Form State
  const [customerEmail, setCustomerEmail] = useState('')
  const [instructions, setInstructions] = useState('')
  const [submittedJob, setSubmittedJob] = useState<FreelanceJob | null>(null)

  // Expandable Job ID
  const [expandedJobId, setExpandedJob] = useState<string | null>(null)

  // Search/Filter states
  const [templateSearch, setToolSearch] = useState('')

  useEffect(() => {
    fetchTemplates()
    fetchJobs()
  }, [])

  const handleCreateOrderSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!customerEmail || !specificInstructions || !selectedTemplate) return

    const orderDetails = {
      customer_email: customerEmail,
      details: specificInstructions
    }

    const createdJob = await createOrder(selectedTemplate.id, {
      customer_email: customerEmail,
      details: specificInstructions
    })

    if (createdJob) {
      setSubmittedJob(createdJob)
    }
  }

  // Filter templates
  const filteredTemplates = templates.filter(
    (t) =>
      t.name.toLowerCase().includes(templateSearch.toLowerCase()) ||
      t.description.toLowerCase().includes(templateSearch.toLowerCase())
  )

  const [selectedTemplateForOrder, setSelectedTemplateForOrder] = useState<TaskTemplate | null>(null)
  const [customerEmailState, setCustomerEmailState] = useState('')
  const [instructionsState, setInstructionsState] = useState('')
  const [createdOrderState, setCreatedOrderState] = useState<FreelanceJob | null>(null)

  const handleOrderSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedTemplateForOrder) return

    const res = await createOrder(selectedTemplateForOrder.id, {
      customer_email: customerEmailState,
      specific_instructions: instructionsState
    })

    if (res) {
      setCreatedOrderState(res)
      // Clear forms
      setCustomerEmailState('')
      setInstructionsState('')
    }
  }

  const getStatusBadgeStyle = (status: FreelanceJob['status']) => {
    switch (status) {
      case 'delivered':
        return 'bg-green-500/10 text-green-500 border-green-500/20'
      case 'completed':
        return 'bg-blue-500/10 text-blue-500 border-blue-500/20'
      case 'processing':
        return 'bg-amber-500/10 text-amber-500 border-amber-500/20 animate-pulse'
      case 'paid':
      default:
        return 'bg-purple-500/10 text-purple-500 border-purple-500/20'
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fadeIn">
      <div className="w-full max-w-5xl h-[85vh] bg-white dark:bg-slate-900 rounded-2xl shadow-2xl overflow-hidden flex flex-col border border-slate-200 dark:border-slate-800">
        
        {/* Header */}
        <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-950/20">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-green-500/10 text-green-500 rounded-xl border border-green-500/20">
              <DollarSign size={20} />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Jarvis Freelancer Dashboard</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">Offer, execute, and deliver automated paid AI services</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Analytics Banner */}
        <div className="grid grid-cols-1 sm:grid-cols-3 border-b border-slate-200 dark:border-slate-800 bg-slate-50/30 dark:bg-slate-950/5">
          <div className="p-5 border-r border-slate-200 dark:border-slate-800 flex flex-col justify-center">
            <span className="text-xs text-slate-400 dark:text-slate-500 uppercase tracking-wider font-semibold">Total Revenue Earned</span>
            <div className="flex items-baseline gap-1 mt-1">
              <span className="text-2xl font-bold text-slate-900 dark:text-white">${earnings.total_earned}</span>
              <span className="text-xs text-green-500 font-semibold">USD</span>
            </div>
          </div>
          <div className="p-5 border-r border-slate-200 dark:border-slate-800 flex flex-col justify-center">
            <span className="text-xs text-slate-400 dark:text-slate-500 uppercase tracking-wider font-semibold">Completed Tasks</span>
            <div className="mt-1">
              <span className="text-2xl font-bold text-slate-900 dark:text-white">{earnings.completed_jobs}</span>
              <span className="text-xs text-slate-400 dark:text-slate-500 ml-2.5">jobs delivered</span>
            </div>
          </div>
          <div className="p-5 flex flex-col justify-center">
            <span className="text-xs text-slate-400 dark:text-slate-500 uppercase tracking-wider font-semibold">Active Queue</span>
            <div className="mt-1">
              <span className="text-2xl font-bold text-amber-500">
                {jobs.filter((j) => j.status === 'processing' || j.status === 'paid').length}
              </span>
              <span className="text-xs text-slate-400 dark:text-slate-500 ml-2.5">jobs running</span>
            </div>
          </div>
        </div>

        {/* Navigation Toolbar */}
        <div className="flex border-b border-slate-200 dark:border-slate-800 bg-slate-50/10 dark:bg-slate-950/10 px-4 justify-between items-center">
          <div className="flex gap-2">
            {(['available', 'jobs'] as TabType[]).map((tab) => {
              const isActive = activeTab === tab
              return (
                <button
                  key={tab}
                  onClick={() => {
                    setActiveTab(tab)
                    setSelectedTemplateForOrder(null)
                    setCreatedOrderState(null)
                  }}
                  className={`px-4 py-3 text-sm font-medium border-b-2 transition-all capitalize ${
                    isActive
                      ? 'border-green-600 text-green-600 dark:border-green-500 dark:text-green-400'
                      : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
                  }`}
                >
                  {tab === 'available' ? 'Available Task Catalog' : 'My Jobs & History'}
                </button>
              )
            })}
          </div>

          {activeTab === 'available' && (
            <div className="relative w-64 mr-2 py-1.5">
              <Search className="absolute left-2.5 top-3.5 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search catalog..."
                value={templateSearch}
                onChange={(e) => setToolSearch(e.target.value)}
                className="w-full bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white rounded-lg pl-8 pr-3 py-1.5 text-xs border border-slate-200 dark:border-slate-800/80 focus:outline-none focus:ring-1 focus:ring-green-500"
              />
            </div>
          )}
        </div>

        {/* Body Area */}
        <div className="flex-1 overflow-y-auto p-6 bg-slate-50/20 dark:bg-slate-950/5">
          {error && (
            <div className="mb-4 p-3.5 rounded-xl bg-red-500/10 text-red-500 border border-red-500/10 flex items-center gap-3 text-sm animate-shake">
              <AlertCircle size={18} className="flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* AVAILABLE TASKS CATALOG TAB */}
          {activeTab === 'available' && (
            <div className="h-full">
              {!selectedTemplateForOrder ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  {filteredTemplates.map((template) => (
                    <div
                      key={template.id}
                      className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800/80 p-5 rounded-2xl flex flex-col justify-between hover:border-green-500/30 dark:hover:border-green-500/30 hover:shadow-lg transition-all"
                    >
                      <div>
                        <div className="flex justify-between items-start mb-2">
                          <h4 className="font-bold text-slate-800 dark:text-white text-base">{template.name}</h4>
                          <span className="text-green-600 dark:text-green-400 font-extrabold font-mono text-lg">
                            ${template.price}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed mb-4">
                          {template.description}
                        </p>
                      </div>

                      <div className="flex items-center justify-between border-t border-slate-100 dark:border-slate-800/60 pt-3.5 mt-2">
                        <div className="flex items-center gap-1 text-slate-400 dark:text-slate-500 text-xs">
                          <Clock size={13} />
                          <span>Est. {template.estimated_time}</span>
                        </div>
                        <button
                          onClick={() => {
                            setSelectedTemplateForOrder(template)
                            setCreatedOrderState(null)
                          }}
                          className="px-3.5 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
                        >
                          <Plus size={13} />
                          <span>Order Task</span>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                /* Submission Order Form */
                <div className="max-w-xl mx-auto bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-xl animate-scaleIn">
                  <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800/60 pb-3 mb-4">
                    <div>
                      <span className="text-xs font-semibold text-green-600 dark:text-green-400 uppercase tracking-wider">New Order</span>
                      <h3 className="font-bold text-slate-900 dark:text-white">{selectedTemplateForOrder.name}</h3>
                    </div>
                    <button
                      onClick={() => setSelectedTemplateForOrder(null)}
                      className="p-1 hover:bg-slate-100 dark:hover:bg-slate-800 rounded text-slate-400 hover:text-slate-600"
                    >
                      Cancel
                    </button>
                  </div>

                  {!createdOrderState ? (
                    <form onSubmit={handleOrderSubmit} className="space-y-4">
                      <div>
                        <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1.5">
                          Customer Email Address
                        </label>
                        <input
                          type="email"
                          required
                          placeholder="e.g. support@customer.com"
                          value={customerEmailState}
                          onChange={(e) => setCustomerEmailState(e.target.value)}
                          className="w-full bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white rounded-lg px-3 py-2 text-sm border border-slate-200 dark:border-slate-800 focus:outline-none focus:ring-1 focus:ring-green-500"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1.5">
                          Specific Task Instructions & Details
                        </label>
                        <textarea
                          required
                          rows={4}
                          placeholder="Please specify target website URLs, copywriting directions, test parameters or required formats..."
                          value={instructionsState}
                          onChange={(e) => setInstructionsState(e.target.value)}
                          className="w-full bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white rounded-lg px-3 py-2 text-sm border border-slate-200 dark:border-slate-800 focus:outline-none focus:ring-1 focus:ring-green-500"
                        />
                      </div>

                      <div className="p-3 bg-slate-50 dark:bg-slate-950/20 rounded-xl border border-slate-100 dark:border-slate-800 flex justify-between items-center text-xs">
                        <span className="text-slate-500">Service Price:</span>
                        <span className="font-bold text-green-600 dark:text-green-400 text-sm">
                          ${selectedTemplateForOrder.price}
                        </span>
                      </div>

                      <button
                        type="submit"
                        disabled={isProcessing}
                        className="w-full py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-xl text-sm font-semibold transition-colors shadow-md flex items-center justify-center gap-2"
                      >
                        {isProcessing ? (
                          <>
                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                            <span>Generating Order...</span>
                          </>
                        ) : (
                          <>
                            <CreditCard size={15} />
                            <span>Confirm Order & Pay</span>
                          </>
                        )}
                      </button>
                    </form>
                  ) : (
                    /* Post-Order Stripe Redirect */
                    <div className="space-y-5 py-4 text-center">
                      <div className="w-12 h-12 bg-green-500/10 text-green-500 rounded-full flex items-center justify-center mx-auto border border-green-500/20">
                        <CheckCircle size={24} />
                      </div>
                      <div>
                        <h4 className="font-bold text-slate-900 dark:text-white text-base">Order Initialized Successfully!</h4>
                        <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
                          To activate execution, proceed to complete your mock Stripe payment flow below.
                        </p>
                      </div>

                      <div className="p-4 bg-slate-50 dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 text-left space-y-2">
                        <div className="flex justify-between text-xs">
                          <span className="text-slate-400">Order ID:</span>
                          <span className="font-mono font-semibold text-slate-700 dark:text-slate-300">{createdOrderState.id}</span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-slate-400">Service Amount:</span>
                          <span className="font-bold text-green-600 dark:text-green-400">${createdOrderState.amount_paid}</span>
                        </div>
                      </div>

                      <div className="flex flex-col gap-2.5">
                        <a
                          href={createdOrderState.payment_url}
                          target="_blank"
                          rel="noreferrer"
                          className="py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-semibold flex items-center justify-center gap-1.5 transition-colors shadow-md"
                        >
                          <span>Proceed to Stripe Checkout</span>
                          <ExternalLink size={14} />
                        </a>
                        <button
                          onClick={() => {
                            setSelectedTemplateForOrder(null)
                            setCreatedOrderState(null)
                            setActiveTab('jobs')
                          }}
                          className="py-2.5 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl text-xs font-semibold transition-colors"
                        >
                          View Job Queue
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* MY JOBS & HISTORY TAB */}
          {activeTab === 'jobs' && (
            <div className="space-y-4">
              {isLoading && jobs.length === 0 ? (
                <div className="py-12 flex flex-col items-center justify-center text-slate-400">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600 mb-2"></div>
                  <p className="text-sm">Fetching job catalog list...</p>
                </div>
              ) : jobs.length === 0 ? (
                <div className="py-12 text-center text-slate-400 flex flex-col items-center justify-center space-y-2.5 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800">
                  <History size={36} className="opacity-40" />
                  <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">No freelance jobs recorded</p>
                  <p className="text-xs text-slate-500 max-w-xs mx-auto">Orders you place on task templates will show up here to monitor execution state.</p>
                </div>
              ) : (
                <div className="space-y-3.5">
                  {jobs.map((job) => {
                    const isExpanded = expandedLog === job.id
                    const statusBadge = getStatusBadge(job.status)

                    return (
                      <div
                        key={job.id}
                        className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden bg-white dark:bg-slate-900/60 hover:border-slate-300 dark:hover:border-slate-700 transition-colors shadow-sm"
                      >
                        {/* Header card button */}
                        <button
                          onClick={() => setExpandedJob(isExpanded ? null : job.id)}
                          className="w-full p-4 flex flex-col sm:flex-row sm:items-center justify-between text-left gap-3 text-xs"
                        >
                          <div className="space-y-1.5">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-bold text-slate-900 dark:text-white text-sm">{job.task_type}</span>
                              <span className="text-[10px] font-mono text-slate-400">#{job.id}</span>
                            </div>
                            <div className="flex items-center gap-3.5 text-slate-400 dark:text-slate-500">
                              <span>Customer: {job.customer_email}</span>
                              <span>•</span>
                              <span>{new Date(job.created_at).toLocaleDateString()}</span>
                            </div>
                          </div>

                          <div className="flex items-center gap-4 justify-between sm:justify-end">
                            <span className="font-mono font-bold text-slate-800 dark:text-slate-200 text-sm">
                              ${job.amount_paid}
                            </span>
                            <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase ${statusBadge}`}>
                              {job.status}
                            </span>
                            {isExpanded ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
                          </div>
                        </button>

                        {/* Expandable details */}
                        {isExpanded && (
                          <div className="p-5 border-t border-slate-100 dark:border-slate-800/80 bg-slate-50/40 dark:bg-slate-950/20 text-xs space-y-4">
                            <div>
                              <span className="block text-slate-400 font-semibold uppercase tracking-wider text-[10px] mb-1">
                                Specific Customer Instructions:
                              </span>
                              <p className="text-slate-700 dark:text-slate-300 font-medium whitespace-pre-wrap">
                                {job.details}
                              </p>
                            </div>

                            {job.summary && (
                              <div className="p-3.5 bg-slate-100/50 dark:bg-slate-900 rounded-xl border border-slate-200/40 dark:border-slate-800/60">
                                <span className="block text-slate-400 font-semibold uppercase tracking-wider text-[10px] mb-1.5">
                                  Job Delivery Summary:
                                </span>
                                <p className="text-slate-700 dark:text-slate-300 font-semibold">
                                  {job.summary}
                                </p>
                              </div>
                            )}

                            {job.deliverables && job.deliverables.length > 0 && (
                              <div>
                                <span className="block text-slate-400 font-semibold uppercase tracking-wider text-[10px] mb-2">
                                  Job Deliverable Files:
                                </span>
                                <div className="flex flex-wrap gap-2">
                                  {job.deliverables.map((deliv, idx) => (
                                    <button
                                      key={idx}
                                      onClick={() => alert(`Downloading deliverable: ${deliv} in mock mode`)}
                                      className="px-3 py-1.5 bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg text-slate-600 dark:text-slate-300 hover:text-green-500 dark:hover:text-green-400 hover:border-green-500/30 flex items-center gap-1.5 transition-all text-xs font-semibold shadow-xs"
                                    >
                                      <Download size={13} />
                                      <span className="truncate max-w-[180px] font-mono">{deliv}</span>
                                    </button>
                                  ))}
                                </div>
                              </div>
                            )}

                            {job.status === 'paid' && (
                              <div className="p-3 rounded-xl bg-purple-500/10 text-purple-600 border border-purple-500/15 text-xs flex items-center gap-2">
                                <AlertCircle size={15} className="flex-shrink-0" />
                                <span>Order is paid and queued. Autonomous execution engine will wake up shortly.</span>
                              </div>
                            )}

                            {job.status === 'processing' && (
                              <div className="p-3 rounded-xl bg-amber-500/10 text-amber-500 border border-amber-500/15 text-xs flex items-center gap-2 animate-pulse">
                                <AlertCircle size={15} className="flex-shrink-0 animate-spin" />
                                <span>Jarvis is currently processing this job autonomously in the backend container...</span>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const getStatusBadge = (status: FreelanceJob['status']) => {
  switch (status) {
    case 'delivered':
      return 'bg-green-500/10 text-green-500 border-green-500/20'
    case 'completed':
      return 'bg-blue-500/10 text-blue-500 border-blue-500/20'
    case 'processing':
      return 'bg-amber-500/10 text-amber-500 border-amber-500/20'
    case 'paid':
    default:
      return 'bg-purple-500/10 text-purple-500 border-purple-500/20'
  }
}
