import React from 'react'
import { BookOpen, ExternalLink, Calendar, Tag } from 'lucide-react'
import { KnowledgeDigest as DigestType } from '../stores/knowledge'

interface KnowledgeDigestProps {
  digest: DigestType | null
  isLoading: boolean
}

export const KnowledgeDigest: React.FC<KnowledgeDigestProps> = ({ digest, isLoading }) => {
  if (isLoading) {
    return (
      <div className="py-16 flex flex-col items-center justify-center text-slate-400">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mb-3"></div>
        <p className="text-sm font-medium">Generating weekly AI digest...</p>
      </div>
    )
  }

  if (!digest) {
    return (
      <div className="py-16 text-center text-slate-400 flex flex-col items-center justify-center space-y-3 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800">
        <BookOpen size={40} className="opacity-30 text-indigo-500 animate-pulse" />
        <p className="text-base font-semibold text-slate-800 dark:text-slate-200">No digest compiled yet</p>
        <p className="text-xs text-slate-500 max-w-sm">
          Jarvis compiles a weekly digest automatically from your active sources. Check back shortly!
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fadeIn max-w-3xl mx-auto">
      {/* Digest Header Hero */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 p-6 sm:p-8 text-white shadow-lg border border-indigo-400/20">
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full -mr-20 -mt-20 blur-xl pointer-events-none"></div>
        <div className="relative z-10 space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-white/10 backdrop-blur-md rounded-full text-xs font-semibold uppercase tracking-wider border border-white/10">
            <Calendar size={12} />
            <span>Compiled {new Date(digest.created_at).toLocaleDateString()}</span>
          </div>
          <h3 className="text-2xl sm:text-3xl font-bold tracking-tight">{digest.title}</h3>
          <p className="text-sm sm:text-base text-indigo-100/90 leading-relaxed font-medium">
            {digest.summary}
          </p>
        </div>
      </div>

      {/* Digest Sections */}
      <div className="space-y-8">
        {digest.sections.map((section, sIdx) => (
          <div key={sIdx} className="space-y-4">
            <div className="flex items-center gap-3 border-b border-slate-100 dark:border-slate-800/80 pb-2">
              <span className="w-2.5 h-2.5 bg-indigo-500 rounded-full"></span>
              <h4 className="text-sm font-bold text-slate-950 dark:text-slate-200 uppercase tracking-wider">
                {section.category}
              </h4>
            </div>

            <div className="grid grid-cols-1 gap-4">
              {section.entries.map((entry, eIdx) => (
                <div
                  key={eIdx}
                  className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800/60 p-5 rounded-xl shadow-xs hover:border-indigo-500/20 dark:hover:border-indigo-500/30 hover:shadow-md transition-all flex flex-col justify-between"
                >
                  <div className="space-y-2">
                    <div className="flex justify-between items-start gap-4">
                      <h5 className="font-bold text-slate-800 dark:text-white text-base hover:text-indigo-600 dark:hover:text-indigo-400 leading-snug">
                        {entry.title}
                      </h5>
                      {entry.url && (
                        <a
                          href={entry.url}
                          target="_blank"
                          rel="noreferrer"
                          className="p-1 hover:bg-slate-100 dark:hover:bg-slate-800 rounded text-slate-400 hover:text-indigo-500 transition-colors"
                        >
                          <ExternalLink size={14} />
                        </a>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                      {entry.summary}
                    </p>
                  </div>

                  {entry.tags && entry.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-3 mt-2 border-t border-slate-50 dark:border-slate-800/40">
                      {entry.tags.map((tag, tIdx) => (
                        <span
                          key={tIdx}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-slate-50 dark:bg-slate-950 text-slate-400 dark:text-slate-500 border border-slate-100 dark:border-slate-800/50"
                        >
                          <Tag size={8} />
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
