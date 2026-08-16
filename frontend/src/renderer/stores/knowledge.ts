import { create } from 'zustand'
import { useAuthStore } from './auth'

export interface KnowledgeEntry {
  id: string
  source_id?: string
  title: string
  summary: string
  content?: string
  url?: string
  source_name: string
  source_category?: string // fallback
  source_type?: string // real backend field
  tags?: string[] // fallback
  topics?: string[] // real backend field
  is_read: boolean
  created_at: string
  published_at?: string
}

export interface DigestEntry {
  title: string
  url?: string
  source_name: string
  summary: string | null
  topics?: string[]
}

export interface KnowledgeDigest {
  generated_at?: string
  created_at?: string // mock fallback
  total_entries?: number
  entries?: DigestEntry[] // real backend flat list
  title?: string // mock fallback
  summary?: string // mock fallback
  sections?: {
    category: string
    entries: {
      title: string
      summary: string
      url?: string
      tags?: string[]
    }[]
  }[] // mock fallback
}

export interface KnowledgeSource {
  id: string
  name: string
  url: string | null
  category?: string // fallback
  source_type?: string // real backend field
  last_fetched_at: string | null
  is_active: bool
}

interface KnowledgeState {
  entries: KnowledgeEntry[]
  digest: KnowledgeDigest | null
  sources: KnowledgeSource[]
  isLoading: boolean
  isProcessing: boolean
  error: string | null

  fetchEntries: () => Promise<void>
  fetchDigest: () => Promise<void>
  fetchSources: () => Promise<void>
  searchKnowledge: (query: string) => Promise<void>
  refreshSource: (id: string) => Promise<void>
  markEntryRead: (id: string) => Promise<void>
}

import { getApiUrl } from '../utils/env'

const API_URL = getApiUrl()

// Default mock sources matching FeedSource schemas
const MOCK_SOURCES: KnowledgeSource[] = [
  { id: 'src-hn', name: 'Hacker News Top Stories (AI/ML)', url: 'https://news.ycombinator.com', source_type: 'hackernews', last_fetched_at: '2026-07-09T08:00:00Z', is_active: true },
  { id: 'src-gh', name: 'GitHub Trending (AI/ML)', url: 'https://github.com/trending', source_type: 'github_trending', last_fetched_at: '2026-07-09T08:15:00Z', is_active: true },
  { id: 'src-openai', name: 'OpenAI API Changelog', url: 'https://platform.openai.com/docs/changelog', source_type: 'changelog', last_fetched_at: '2026-07-08T12:00:00Z', is_active: true },
  { id: 'src-blog', name: 'Shipwright Engineering Blog', url: 'https://shipwright.io/blog', source_type: 'rss', last_fetched_at: '2026-07-07T14:30:00Z', is_active: true }
]

// Default mock entries matching KnowledgeEntry response schema
const MOCK_ENTRIES: KnowledgeEntry[] = [
  {
    id: 'entry-1',
    title: 'Show HN: Llama.node – High-performance offline LLM server for Node.js',
    summary: 'A lightweight Node.js wrapper around llama.cpp that allows running GGUF models directly in-process with minimal memory footprint and zero external dependencies. Features hardware-accelerated metal/CUDA bindings and a streamlined streaming API.',
    url: 'https://github.com/llama-node/llama.node',
    source_name: 'Hacker News Top Stories (AI/ML)',
    source_type: 'hackernews',
    topics: ['AI', 'Local-First', 'NodeJS', 'llama.cpp'],
    is_read: false,
    created_at: '2026-07-09T07:45:00Z'
  },
  {
    id: 'entry-2',
    title: 'vllm-project/vllm: Easy, fast, and cheap LLM serving with PagedAttention',
    summary: 'A high-throughput and memory-efficient LLM serving and inference engine. It uses PagedAttention to manage attention key-value memory with near-zero waste, yielding up to 24x higher throughput than Hugging Face Transformers.',
    url: 'https://github.com/vllm-project/vllm',
    source_name: 'GitHub Trending (AI/ML)',
    source_type: 'github_trending',
    topics: ['Inference', 'LLM', 'High-Throughput', 'Open-Source'],
    is_read: false,
    created_at: '2026-07-09T06:12:00Z'
  },
  {
    id: 'entry-3',
    title: 'LangChain v0.3 Release: Fully Native Python 3.12 Support & Core Decoupling',
    summary: 'LangChain has released v0.3.0. In this release, all core modules are fully decoupled from integration packages to prevent dependency bloat. Native support for Python 3.12 is complete, along with performance improvements in async chain execution pipelines.',
    url: 'https://blog.langchain.dev/langchain-v0-3',
    source_name: 'OpenAI API Changelog',
    source_type: 'changelog',
    topics: ['LangChain', 'Python3.12', 'Release', 'decoupling'],
    is_read: true,
    created_at: '2026-07-08T11:45:00Z'
  },
  {
    id: 'entry-4',
    title: 'Building private vector databases on the edge with SQLite and vector extensions',
    summary: 'A deep dive on leveraging SQLite with modular custom vector extensions (like sqlite-vss) to build lightning-fast, zero-overhead semantic search directly inside edge or electron applications, bypassing heavy database services.',
    url: 'https://shipwright.io/blog/sqlite-vector-databases-on-the-edge',
    source_name: 'Shipwright Engineering Blog',
    source_type: 'rss',
    topics: ['SQLite', 'Vector-DB', 'Edge', 'Semantic-Search'],
    is_read: false,
    created_at: '2026-07-07T14:15:00Z'
  }
]

// Default mock digest matching DigestResponse and DigestEntry schemas
const MOCK_DIGEST: KnowledgeDigest = {
  generated_at: '2026-07-09T09:00:00Z',
  total_entries: 4,
  entries: [
    {
      title: 'Llama.node GGUF execution engine',
      summary: 'In-process streaming execution on local edge nodes with metal hardware acceleration, ideal for modular assistants.',
      url: 'https://github.com/llama-node/llama.node',
      source_name: 'Hacker News Top Stories (AI/ML)',
      topics: ['GGUF', 'Local-First']
    },
    {
      title: 'vLLM high throughput serving v0.5',
      summary: 'Memory-efficient PagedAttention mechanisms boost deployment capacity on shared infrastructure grids.',
      url: 'https://github.com/vllm-project/vllm',
      source_name: 'GitHub Trending (AI/ML)',
      topics: ['vLLM', 'PagedAttention']
    },
    {
      title: 'LangChain v0.3 decoupled core releases',
      summary: 'Allows modular library imports avoiding nested environment package dependency bloat.',
      url: 'https://blog.langchain.dev/langchain-v0-3',
      source_name: 'OpenAI API Changelog',
      topics: ['LangChain', 'Python']
    },
    {
      title: 'SQLite vector search deployment',
      summary: 'A comprehensive layout of running edge semantic querying inside standalone Electron app databases.',
      url: 'https://shipwright.io/blog/sqlite-vector-databases-on-the-edge',
      source_name: 'Shipwright Engineering Blog',
      topics: ['SQLite', 'Edge-AI']
    }
  ]
}

const loadPersistedEntries = (): KnowledgeEntry[] => {
  try {
    const entriesStr = localStorage.getItem('jarvis-knowledge-entries')
    if (entriesStr) {
      return JSON.parse(entriesStr)
    }
  } catch (e) {
    console.error('Failed to parse persisted knowledge entries:', e)
  }
  localStorage.setItem('jarvis-knowledge-entries', JSON.stringify(MOCK_ENTRIES))
  return MOCK_ENTRIES
}

const persistEntries = (entries: KnowledgeEntry[]) => {
  localStorage.setItem('jarvis-knowledge-entries', JSON.stringify(entries))
}

const loadPersistedSources = (): KnowledgeSource[] => {
  try {
    const srcStr = localStorage.getItem('jarvis-knowledge-sources')
    if (srcStr) {
      return JSON.parse(srcStr)
    }
  } catch (e) {
    console.error('Failed to parse persisted knowledge sources:', e)
  }
  localStorage.setItem('jarvis-knowledge-sources', JSON.stringify(MOCK_SOURCES))
  return MOCK_SOURCES
}

const persistSources = (sources: KnowledgeSource[]) => {
  localStorage.setItem('jarvis-knowledge-sources', JSON.stringify(sources))
}

export const useKnowledgeStore = create<KnowledgeState>((set, get) => ({
  entries: [],
  digest: null,
  sources: [],
  isLoading: false,
  isProcessing: false,
  error: null,

  fetchEntries: async () => {
    set({ isLoading: true, error: null })
    try {
      const token = useAuthStore.getState().token
      const response = await fetch(`${API_URL}/api/v1/knowledge/entries`, {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch knowledge entries from backend')
      }

      const data = await response.json()
      // Real API wraps inside an items array
      const entries = Array.isArray(data) ? data : (data.items || loadPersistedEntries())
      set({ entries, isLoading: false })
    } catch (err: any) {
      console.warn('fetchEntries failed, falling back to persisted local entries:', err.message)
      const entries = loadPersistedEntries()
      set({ entries, isLoading: false })
    }
  },

  fetchDigest: async () => {
    set({ isLoading: true, error: null })
    try {
      const token = useAuthStore.getState().token
      const response = await fetch(`${API_URL}/api/v1/knowledge/digest`, {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch weekly digest from backend')
      }

      const data = await response.json()
      set({ digest: data || MOCK_DIGEST, isLoading: false })
    } catch (err: any) {
      console.warn('fetchDigest failed, falling back to mock digest:', err.message)
      set({ digest: MOCK_DIGEST, isLoading: false })
    }
  },

  fetchSources: async () => {
    set({ isLoading: true, error: null })
    try {
      const token = useAuthStore.getState().token
      const response = await fetch(`${API_URL}/api/v1/knowledge/sources`, {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch knowledge sources')
      }

      const data = await response.json()
      const sources = Array.isArray(data) ? data : (data.items || loadPersistedSources())
      set({ sources, isLoading: false })
    } catch (err: any) {
      console.warn('fetchSources failed, falling back to persisted sources:', err.message)
      const sources = loadPersistedSources()
      set({ sources, isLoading: false })
    }
  },

  searchKnowledge: async (query: string) => {
    if (!query.trim()) {
      get().fetchEntries()
      return
    }

    set({ isLoading: true, error: null })
    try {
      const token = useAuthStore.getState().token
      // Real API filters using search parameter directly on entries
      const response = await fetch(`${API_URL}/api/v1/knowledge/entries?search=${encodeURIComponent(query)}`, {
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('Failed to search knowledge base')
      }

      const data = await response.json()
      const entries = Array.isArray(data) ? data : (data.items || [])
      set({ entries, isLoading: false })
    } catch (err: any) {
      console.warn('searchKnowledge failed, running client-side filtering:', err.message)
      const allEntries = loadPersistedEntries()
      const filtered = allEntries.filter(
        (e) =>
          e.title.toLowerCase().includes(query.toLowerCase()) ||
          e.summary.toLowerCase().includes(query.toLowerCase()) ||
          ((e.topics || e.tags || []).some((t) => t.toLowerCase().includes(query.toLowerCase())))
      )
      set({ entries: filtered, isLoading: false })
    }
  },

  refreshSource: async (id: string) => {
    set({ isProcessing: true, error: null })
    try {
      const token = useAuthStore.getState().token
      // Corrected to POST /crawl/{source_id} matching Backend Crawler API
      const response = await fetch(`${API_URL}/api/v1/knowledge/crawl/${id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error('Failed to refresh source on backend')
      }

      // Update source's last_fetched_at locally
      const currentSources = get().sources
      const updatedSources = currentSources.map((src) =>
        src.id === id ? { ...src, last_fetched_at: new Date().toISOString() } : src
      )
      persistSources(updatedSources)
      set({ sources: updatedSources, isProcessing: false })
    } catch (err: any) {
      console.warn(`refreshSource for ${id} failed, performing local mock refresh:`, err.message)
      const currentSources = get().sources.length > 0 ? get().sources : loadPersistedSources()
      const updatedSources = currentSources.map((src) =>
        src.id === id ? { ...src, last_fetched_at: new Date().toISOString() } : src
      )
      persistSources(updatedSources)
      set({ sources: updatedSources, isProcessing: false })
    }
  },

  markEntryRead: async (id: string) => {
    try {
      const token = useAuthStore.getState().token
      // Corrected to POST /entries/{entry_id}/read matching Backend API
      await fetch(`${API_URL}/api/v1/knowledge/entries/${id}/read`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })
      
      const currentEntries = get().entries
      const updatedEntries = currentEntries.map((entry) =>
        entry.id === id ? { ...entry, is_read: true } : entry
      )
      persistEntries(updatedEntries)
      set({ entries: updatedEntries })
    } catch (err: any) {
      console.warn(`markEntryRead for ${id} failed, performing local update:`, err.message)
      const currentEntries = get().entries.length > 0 ? get().entries : loadPersistedEntries()
      const updatedEntries = currentEntries.map((entry) =>
        entry.id === id ? { ...entry, is_read: true } : entry
      )
      persistEntries(updatedEntries)
      set({ entries: updatedEntries })
    }
  }
}))
