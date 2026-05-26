'use client';

import { formatDistanceToNow } from 'date-fns';
import { Sparkles } from 'lucide-react';

interface News {
  id:           string;
  title:        string;
  aiSummary:    string | null;
  url:          string | null;
  source:       string;
  publishedAt:  string;
  sentiment:    string;
  impactScore:  number;
  category:     string;
  isEarlySignal: boolean;
}

// ── Shared sentiment color map ────────────────────────────────────────────────

export interface SentimentStyle {
  borderColor: string;   // left accent bar
  bgTint:      string;   // card background tint
  chip:        string;   // badge classes
  dot:         string;   // colored dot inside chip
  bar:         string;   // impact bar color
  label:       string;   // display label
}

export function sentimentStyle(s: string): SentimentStyle {
  if (s === 'BULLISH') return {
    borderColor: 'border-l-emerald-500',
    bgTint:      'bg-emerald-50/25',
    chip:        'bg-emerald-50 text-emerald-700 border-emerald-200',
    dot:         'bg-emerald-500',
    bar:         'bg-emerald-500',
    label:       'Bullish',
  };
  if (s === 'BEARISH') return {
    borderColor: 'border-l-red-500',
    bgTint:      'bg-red-50/30',
    chip:        'bg-red-50 text-red-600 border-red-200',
    dot:         'bg-red-500',
    bar:         'bg-red-500',
    label:       'Bearish',
  };
  return {
    borderColor: 'border-l-amber-400',
    bgTint:      'bg-amber-50/20',
    chip:        'bg-amber-50 text-amber-700 border-amber-200',
    dot:         'bg-amber-400',
    bar:         'bg-amber-400',
    label:       'Netral',
  };
}

// ── "Diringkas AI" badge ──────────────────────────────────────────────────────

export function DiringkasAiBadge() {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold text-white flex-shrink-0"
      style={{
        background:  'linear-gradient(135deg, #7c3aed 0%, #2563eb 100%)',
        boxShadow:   '0 0 8px rgba(124,58,237,0.25)',
      }}
    >
      <Sparkles className="w-3 h-3 flex-shrink-0" />
      Diringkas AI
    </span>
  );
}

// ── Main card ─────────────────────────────────────────────────────────────────

export default function NewsCard({
  news,
  isMacroImpact,
}: {
  news:           News;
  isMacroImpact?: boolean;
}) {
  const styles = sentimentStyle(news.sentiment);

  return (
    <div
      className={`
        relative bg-white border border-stone-200 border-l-4 ${styles.borderColor}
        ${styles.bgTint} rounded-2xl p-4 pl-5 overflow-hidden
        shadow-sm hover:shadow-md transition-shadow duration-200
      `}
    >
      {/* Badge row */}
      <div className="flex items-center gap-2 mb-2 flex-wrap">

        {/* Sentiment chip — vivid with colored dot */}
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold border flex-shrink-0 ${styles.chip}`}
        >
          <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${styles.dot}`} />
          {styles.label}
        </span>

        {/* Diringkas AI badge */}
        {news.aiSummary && <DiringkasAiBadge />}

        {/* Macro impact */}
        {isMacroImpact && (
          <span
            className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-violet-50 text-violet-700 border border-violet-200 flex-shrink-0"
            title="Potensi dampak sentimen — bukan berita langsung tentang emiten ini"
          >
            Dampak makro
          </span>
        )}

        {/* Early signal */}
        {news.isEarlySignal && (
          <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 flex-shrink-0">
            Signal
          </span>
        )}

        {/* Category — muted */}
        <span className="text-xs text-stone-400 ml-auto">{news.category}</span>
      </div>

      {/* Title */}
      <h3 className="text-sm font-bold text-stone-900 leading-snug mb-2 line-clamp-2">
        {news.title}
      </h3>

      {/* AI Summary */}
      {news.aiSummary && (
        <p className="text-xs text-stone-600 leading-relaxed mb-3">
          {news.aiSummary}
        </p>
      )}

      {/* Impact bar — sentiment-colored, width = impactScore × 10% */}
      <div className="mb-3">
        <div className="flex justify-between text-xs text-stone-400 mb-1">
          <span>Dampak</span>
          <span className="font-semibold text-stone-600">
            {news.impactScore.toFixed(1)}
            <span className="font-normal text-stone-400">/10</span>
          </span>
        </div>
        <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden">
          <div
            className={`h-1.5 rounded-full transition-all ${styles.bar}`}
            style={{ width: `${(news.impactScore / 10) * 100}%` }}
          />
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-stone-100/80">
        <span className="text-xs text-stone-400">
          <span className="font-medium text-stone-500">{news.source}</span>
          {' · '}
          {formatDistanceToNow(new Date(news.publishedAt), { addSuffix: true })}
        </span>
        {news.url && (
          <a
            href={news.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-brand-600 hover:text-brand-700 font-semibold transition-colors flex-shrink-0 ml-2"
          >
            Baca →
          </a>
        )}
      </div>
    </div>
  );
}
