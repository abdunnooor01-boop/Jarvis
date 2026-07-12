import React, { useState, useEffect } from 'react'
import {
  X,
  Search,
  BookOpen,
  Calendar,
  Tag,
  Check,
  CheckCircle,
  RefreshCw,
  ExternalLink,
  Sliders,
  Rss,
  Layers,
  FileText,
  AlertCircle
} from 'lucide-react'
import { useKnowledgeStore, KnowledgeEntry, KnowledgeSource } from '../stores/knowledge'
import { KnowledgeDigest } from './KnowledgeDigest'

interface KnowledgeFeedProps {
  onClose: () => void
}

type TabType = 'feed' | 'digest' | 'sources'

export const KnowledgeFeed: React.FC<KnowledgeFeedProps> = ({ onClose }) => {
  const {
    entries,
    digest,
    sources,
    isLoading,
    isProcessing,
    error,
    fetchEntries,
    fetchDigest,
    fetchSources,
    searchKnowledge,
    refreshSource,
    markEntryRead
  } = useKnowledgeStore()

  const [activeTab, setActiveTab] = useState<TabType>('feed')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('all')

  useEffect(() => {
    fetchEntries()
    fetchDigest()
    fetchSources()
  }, [])

  // Debounced search logic
  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      searchKnowledge(searchQuery)
    }, 300)

    return () => clearTimeout(delayDebounceFn)
  }, [searchQuery])

  // Filter entries locally by source category (as additional visual filter on top of search)
  const filteredEntries = entries.filter((entry) => {
    if (selectedCategory === 'all') return true
    return entry.source_category === selectedCategory
  })

  const getCategoryBadgeStyle = (category: string) => {
    switch (category) {
      case 'hn':
        return 'bg-orange-500/10 text-orange-600 border-orange-500/20'
      case 'github':
        return 'bg-slate-800/10 text-slate-700 dark:text-slate-300 border-slate-800/20'
      case 'api-changelog':
        return 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20'
      case 'tech-blog':
      default:
        return 'bg-indigo-500/10 text-indigo-600 border-indigo-500/20'
    }
  }

  const formatCategoryName = (category: string) => {
    switch (category) {
      case 'hn':
        return 'Hacker News'
      case 'github':
        return 'GitHub Trending'
      case 'api-changelog':
        return 'API Updates'
      case 'tech-blog':
        return 'Tech Blogs'
      default:
        return category
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fadeIn">
      <div className="w-full max-w-5xl h-[85vh] bg-white dark:bg-slate-900 rounded-2xl shadow-2xl overflow-hidden flex flex-col border border-slate-200 dark:border-slate-800">
        
        {/* Header */}
        <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-950/20">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-indigo-500/10 text-indigo-500 rounded-xl border border-indigo-500/20">
              <BookOpen size={20} className="animate-pulse" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Jarvis Knowledge Hub</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">Curated feeds, API changelogs, and weekly AI developments digest</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Navigation Toolbar */}
        <div className="flex border-b border-slate-200 dark:border-slate-800 bg-slate-50/10 dark:bg-slate-950/10 px-4 justify-between items-center flex-shrink-0">
          <div className="flex gap-2">
            {(['feed', 'digest', 'sources'] as TabType[]).map((tab) => {
              const isActive = activeTab === tab
              return (
                <button
                  key={tab}
                  onClick={() => {
                    setActiveTab(tab)
                    setSearchQuery('')
                    setSelectedCategory('all')
                  }}
                  className={`px-4 py-3 text-sm font-medium border-b-2 transition-all flex items-center gap-2 ${
                    isActive
                      ? 'border-indigo-600 text-indigo-600 dark:border-indigo-500 dark:text-indigo-400'
                      : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
                  }`}
                >
                  {tab === 'feed' && <Rss size={14} />}
                  {tab === 'digest' && <FileText size={14} />}
                  {tab === 'sources' && <Sliders size={14} />}
                  {tab === 'feed' ? 'Knowledge Feed' : tab === 'digest' ? 'Weekly Digest' : 'Manage Sources'}
                </button>
              )
            })}
          </div>

          {activeTab === 'feed' && (
            <div className="relative w-64 mr-2 py-1.5">
              <Search className="absolute left-2.5 top-3.5 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Semantic search news, tags..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white rounded-lg pl-8 pr-3 py-1.5 text-xs border border-slate-200 dark:border-slate-800/80 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          )}
        </div>

        {/* Body Area */}
        <div className="flex-1 overflow-y-auto p-6 bg-slate-50/20 dark:bg-slate-950/5">
          {error && (
            <div className="mb-4 p-3.5 rounded-xl bg-red-500/10 text-red-500 border border-red-500/10 flex items-center gap-3 text-sm">
              <AlertCircle size={18} className="flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* KNOWLEDGE FEED TAB */}
          {activeTab === 'feed' && (
            <div className="space-y-6 h-full flex flex-col">
              {/* Category Filter Pills */}
              <div className="flex flex-wrap gap-2 pb-2 border-b border-slate-100 dark:border-slate-800/40">
                <button
                  onClick={() => setSelectedCategory('all')}
                  className={`px-3 py-1 rounded-full text-xs font-semibold border transition-all ${
                    selectedCategory === 'all'
                      ? 'bg-indigo-600 text-white border-indigo-600'
                      : 'bg-white dark:bg-slate-900 text-slate-500 dark:text-slate-400 border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50'
                  }`}
                >
                  All Feeds
                </button>
                {['hn', 'github', 'api-changelog', 'tech-blog'].map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setSelectedCategory(cat)}
                    className={`px-3 py-1 rounded-full text-xs font-semibold border transition-all ${
                      selectedCategory === cat
                        ? 'bg-indigo-600 text-white border-indigo-600'
                        : 'bg-white dark:bg-slate-900 text-slate-500 dark:text-slate-400 border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50'
                    }`}
                  >
                    {formatCategoryName(cat)}
                  </button>
                ))}
              </div>

              {/* Feed List Grid */}
              <div className="flex-1">
                {isLoading && entries.length === 0 ? (
                  <div className="py-24 flex flex-col items-center justify-center text-slate-400">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mb-3"></div>
                    <p className="text-sm font-medium">Querying vector storage...</p>
                  </div>
                ) : filteredEntries.length === 0 ? (
                  <div className="py-16 text-center text-slate-400 flex flex-col items-center justify-center space-y-3 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800">
                    <Layers size={36} className="opacity-40" />
                    <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">No knowledge entries found</p>
                    <p className="text-xs text-slate-500">
                      Try resetting your search query or enabling other category filter pills.
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {filteredEntries.map((entry) => (
                      <div
                        key={entry.id}
                        className={`bg-white dark:bg-slate-900 border p-5 rounded-2xl flex flex-col justify-between hover:shadow-md transition-all relative ${
                          entry.is_read
                            ? 'border-slate-200 dark:border-slate-800/60 opacity-75'
                            : 'border-slate-200 dark:border-slate-800 shadow-sm ring-1 ring-indigo-500/5'
                        }`}
                      >
                        {/* Unread marker */}
                        {!entry.is_read && (
                          <span className="absolute top-4 right-4 w-2 h-2 bg-indigo-500 rounded-full"></span>
                        )}

                        <div className="space-y-3">
                          <div className="space-y-1">
                            {/* Category & Date */}
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold border uppercase ${getCategoryBadgeStyle(entry.source_category)}`}>
                                {formatCategoryName(entry.source_category)}
                              </span>
                              <span className="text-[10px] text-slate-400 dark:text-slate-500 flex items-center gap-1">
                                <Calendar size={10} />
                                {new Date(entry.created_at).toLocaleDateString()}
                              </span>
                            </div>

                            {/* Title */}
                            <h4 className="font-bold text-slate-800 dark:text-white text-base leading-snug hover:text-indigo-600 dark:hover:text-indigo-400">
                              {entry.url ? (
                                <a href={entry.url} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 inline-flex">
                                  <span>{entry.title}</span>
                                  <ExternalLink size={12} className="flex-shrink-0 text-slate-400" />
                                </a>
                              ) : (
                                entry.title
                              )}
                            </h4>
                          </div>

                          {/* Summary */}
                          <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed line-clamp-3">
                            {entry.summary}
                          </p>
                        </div>

                        {/* Card Footer tags and action */}
                        <div className="flex items-center justify-between border-t border-slate-100 dark:border-slate-800/60 pt-3 mt-4">
                          <div className="flex flex-wrap gap-1 max-w-[70%]">
                            {entry.tags.slice(0, 3).map((tag, tIdx) => (
                              <span
                                key={tIdx}
                                className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold bg-slate-50 dark:bg-slate-950 text-slate-400 dark:text-slate-500 border border-slate-100 dark:border-slate-800/50"
                              >
                                {tag}
                              </span>
                            ))}
                          </div>

                          {!entry.is_read ? (
                            <button
                              onClick={() => markEntryRead(entry.id)}
                              className="px-2.5 py-1 text-[10px] bg-slate-100 hover:bg-indigo-50 dark:bg-slate-800 dark:hover:bg-slate-700/80 text-slate-600 dark:text-slate-300 hover:text-indigo-600 rounded-md font-bold transition-all flex items-center gap-1 border border-slate-200/40 dark:border-slate-700"
                            >
                              <Check size={11} />
                              <span>Mark Read</span>
                            </button>
                          ) : (
                            <span className="text-[10px] text-slate-400 flex items-center gap-1 italic font-medium pr-1.5">
                              <CheckCircle size={11} className="text-green-500" />
                              Read
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* WEEKLY DIGEST TAB */}
          {activeTab === 'digest' && (
            <KnowledgeDigest digest={digest} isLoading={isLoading} />
          )}

          {/* SOURCE MANAGEMENT TAB */}
          {activeTab === 'sources' && (
            <div className="max-w-4xl mx-auto space-y-6 animate-fadeIn">
              <div className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-sm overflow-hidden">
                <div className="p-5 border-b border-slate-100 dark:border-slate-800/60 bg-slate-50/50 dark:bg-slate-950/20">
                  <h4 className="font-bold text-slate-900 dark:text-white text-base">Monitored Knowledge Sources</h4>
                  <p className="text-xs text-slate-500 mt-1">Configured feed collectors and periodic ingestion triggers</p>
                </div>

                <div className="divide-y divide-slate-100 dark:divide-slate-800">
                  {sources.map((source) => (
                    <div key={source.id} className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-bold text-slate-900 dark:text-white text-sm">{source.name}</span>
                          <span className={`px-2 py-0.5 rounded-md text-[9px] font-bold border uppercase ${getCategoryBadgeStyle(source.category)}`}>
                            {formatCategoryName(source.category)}
                          </span>
                        </div>
                        <div className="flex items-center gap-3.5 text-xs text-slate-400 dark:text-slate-500 flex-wrap">
                          <a
                            href={source.url}
                            target="_blank"
                            rel="noreferrer"
                            className="hover:underline flex items-center gap-1 hover:text-indigo-500 transition-colors"
                          >
                            <span>Visit Feed</span>
                            <ExternalLink size={10} />
                          </a>
                          <span>•</span>
                          <span>
                            Last Ingested:{' '}
                            {source.last_fetched_at
                              ? new Date(source.last_fetched_at).toLocaleString()
                              : 'Never'}
                          </span>
                        </div>
                      </div>

                      <button
                        onClick={() => refreshSource(source.id)}
                        disabled={isProcessing}
                        className="self-start sm:self-center px-3.5 py-1.5 border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 rounded-xl text-xs font-bold text-slate-700 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors flex items-center gap-1.5 shadow-sm disabled:opacity-50"
                      >
                        <RefreshCw size={13} className={isProcessing ? 'animate-spin' : ''} />
                        <span>Trigger Refresh</span>
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
