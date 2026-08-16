export interface KnowledgeEntry {
  id: string
  source_id?: string
  title: string
  summary: string
  content?: string
  url?: string
  source_name: string
  source_category?: string
  source_type?: string
  tags?: string[]
  topics?: string[]
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
  created_at?: string
  total_entries?: number
  entries?: DigestEntry[]
  title?: string
  summary?: string
  sections?: {
    category: string
    entries: {
      title: string
      summary: string
      url?: string
      tags?: string[]
    }[]
  }[]
}

export interface KnowledgeSource {
  id: string
  name: string
  url: string | null
  category?: string
  source_type?: string
  last_fetched_at: string | null
  is_active: boolean
}
