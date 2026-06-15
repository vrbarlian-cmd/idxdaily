'use client';

import { formatDistanceToNow } from 'date-fns';

function decodeHTML(str: string): string {
  return str
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}
import { id as localeId } from 'date-fns/locale';
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
  borderColor: string;
  bgTint:      string;
  chip:        string;
  dot:         string;
  bar:         string;
  label:       string;
}

function scoreColor(s: string): string {
  if (s === 'BULLISH') return 'text-[#1D9E75]';
  if (s === 'BEARISH') return 'text-[#E24B4A]';
  if (s === 'NEUTRAL')  return 'text-[#F59E0B]';
  return 'text-[#94A3B8]';
}

export function sentimentStyle(s: string): SentimentStyle {
  if (s === 'BULLISH') return {
    borderColor: 'border-l-emerald-500',
    bgTint:      'bg-emerald-50/10',
    chip:        'bg-emerald-50 text-emerald-700 border-emerald-200',
    dot:         'bg-emerald-500',
    bar:         'bg-emerald-400',
    label:       'Bullish',
  };
  if (s === 'BEARISH') return {
    borderColor: 'border-l-red-500',
    bgTint:      'bg-red-50/15',
    chip:        'bg-red-50 text-red-600 border-red-200',
    dot:         'bg-red-500',
    bar:         'bg-red-400',
    label:       'Bearish',
  };
  return {
    borderColor: 'border-l-amber-400',
    bgTint:      '',
    chip:        'bg-amber-50 text-amber-700 border-amber-200',
    dot:         'bg-amber-400',
    bar:         'bg-amber-400',
    label:       'Netral',
  };
}

// ── AI summary badge ──────────────────────────────────────────────────────────

export function DiringkasAiBadge() {
  return (
    <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-[#1a56db] flex-shrink-0">
      <Sparkles className="w-2.5 h-2.5" />
      AI
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
        relative bg-white border border-[#e5e2db] border-l-4 ${styles.borderColor}
        ${styles.bgTint} rounded-xl p-4 pl-5 overflow-hidden
        hover:shadow-sm transition-shadow duration-200
      `}
    >
      {/* Badge row */}
      <div className="flex items-center gap-2 mb-2 flex-wrap">

        {/* Sentiment chip */}
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold border flex-shrink-0 ${styles.chip}`}>
          <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${styles.dot}`} />
          {styles.label}
        </span>

        {/* AI badge */}
        {news.aiSummary && <DiringkasAiBadge />}

        {/* Macro impact */}
        {isMacroImpact && (
          <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-violet-50 text-violet-700 border border-violet-100 flex-shrink-0">
            Dampak makro
          </span>
        )}

        {/* Early signal */}
        {news.isEarlySignal && (
          <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-amber-50 text-amber-700 border border-amber-100 flex-shrink-0">
            Signal
          </span>
        )}

        {/* Source (top-right, full width available) */}
        <div className="ml-auto flex items-center gap-1.5 min-w-0">
          <span className="font-medium text-[11px] text-[#6b7280] truncate">{news.source}</span>
          {news.category && <span className="text-[10px] text-[#9ca3af] flex-shrink-0">· {news.category}</span>}
        </div>
      </div>

      {/* Title */}
      <h3 className="text-sm font-bold text-[#0f172a] leading-snug mb-2 line-clamp-2">
        {decodeHTML(news.title)}
      </h3>

      {/* AI Summary */}
      {news.aiSummary && (
        <p className="text-[13px] text-[#374151] leading-[1.6] mb-3">
          {news.aiSummary}
        </p>
      )}

      {/* Impact bar */}
      <div className="mb-3">
        <div className="flex items-baseline justify-between mb-1.5">
          <span className="text-[11px] text-[#9ca3af] uppercase tracking-wide">Dampak AI</span>
          <span className={`text-[14px] font-medium ${scoreColor(news.sentiment)}`}>
            {news.impactScore.toFixed(1)}
            <span className="text-[12px] font-normal text-[#9ca3af]">/10</span>
          </span>
        </div>
        <div className="h-1 bg-[#f0ede8] rounded-full overflow-hidden">
          <div
            className={`h-1 rounded-full transition-all ${styles.bar}`}
            style={{ width: `${(news.impactScore / 10) * 100}%` }}
          />
        </div>
      </div>

      {/* Footer: time + Baca → */}
      <div className="flex items-center justify-between pt-2 border-t border-[#f0ede8]">
        <span className="text-[11px] text-[#9ca3af]">
          {formatDistanceToNow(new Date(news.publishedAt), { addSuffix: true, locale: localeId })}
        </span>
        {news.url && (
          <a
            href={news.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] text-[#1a56db] hover:text-blue-700 font-semibold transition-colors flex-shrink-0 ml-2"
          >
            Baca →
          </a>
        )}
      </div>
    </div>
  );
}
