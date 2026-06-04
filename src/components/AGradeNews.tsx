'use client';

import { Sparkles } from 'lucide-react';
import Link from 'next/link';
import { format, formatDistanceToNow, isToday } from 'date-fns';
import { id as localeId } from 'date-fns/locale';
import useSWR from 'swr';
import { useState } from 'react';

// ── Helpers ───────────────────────────────────────────────────────────────────

function accentBar(s: string) {
  if (s === 'BULLISH') return 'border-l-emerald-500';
  if (s === 'BEARISH') return 'border-l-red-500';
  return 'border-l-amber-400';
}
function bgTint(s: string) {
  if (s === 'BULLISH') return 'bg-emerald-50/10';
  if (s === 'BEARISH') return 'bg-red-50/15';
  return '';
}
function sentimentDot(s: string) {
  if (s === 'BULLISH') return 'bg-emerald-500';
  if (s === 'BEARISH') return 'bg-red-500';
  return 'bg-amber-400';
}
function sentimentTextColor(s: string) {
  if (s === 'BULLISH') return 'text-emerald-700';
  if (s === 'BEARISH') return 'text-red-600';
  return 'text-amber-700';
}
function sentimentLabel(s: string) {
  if (s === 'BULLISH') return 'Bullish';
  if (s === 'BEARISH') return 'Bearish';
  return 'Netral';
}
function impactBarColor(s: string) {
  if (s === 'BULLISH') return 'bg-emerald-400';
  if (s === 'BEARISH') return 'bg-red-400';
  return 'bg-amber-400';
}
function impactScoreColor(s: string) {
  if (s === 'BULLISH') return 'text-[#1D9E75]';
  if (s === 'BEARISH') return 'text-[#E24B4A]';
  if (s === 'NEUTRAL')  return 'text-[#F59E0B]';
  return 'text-[#94A3B8]';
}

function isMarketHours(): boolean {
  const wibHour = new Date(
    new Date().toLocaleString('en-US', { timeZone: 'Asia/Jakarta' })
  ).getHours();
  return wibHour >= 9 && wibHour < 16;
}

// ── Types ─────────────────────────────────────────────────────────────────────

interface ArticleData {
  id:          string;
  title:       string;
  aiSummary:   string | null;
  url:         string | null;
  source:      string;
  publishedAt: string | null;   // ISO string from JSON
  sentiment:   string;
  impactScore: number;
  ticker?:     { symbol: string } | null;
  category?:   string | null;
}

// ── Date display ──────────────────────────────────────────────────────────────

function PubDate({ dateStr }: { dateStr: string | null }) {
  if (!dateStr) return null;
  const date = new Date(dateStr);
  if (isToday(date)) {
    const wib = date.toLocaleTimeString('id-ID', {
      hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta',
    });
    return <span className="text-[11px] text-[#9ca3af] tabular-nums">{wib} WIB</span>;
  }
  const label = format(date, 'd MMM', { locale: localeId });
  const ago   = formatDistanceToNow(date, { addSuffix: true, locale: localeId });
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-100">
      {label} · {ago}
    </span>
  );
}

// ── Article card ──────────────────────────────────────────────────────────────

function ArticleCard({ a }: { a: ArticleData }) {
  return (
    <div
      className={`
        relative bg-white border border-[#e5e2db] border-l-4 ${accentBar(a.sentiment)}
        ${bgTint(a.sentiment)} rounded-xl overflow-hidden
        transition-shadow duration-200 hover:shadow-sm
      `}
    >
      <div className="p-4 pl-5">

        {/* Meta row */}
        <div className="flex items-center gap-2 mb-2.5 flex-wrap">

          {/* Ticker chip */}
          {a.ticker && (
            <Link
              href={`/saham/${a.ticker.symbol}`}
              className="font-mono text-[10px] font-bold bg-[#0f172a] hover:bg-[#1e293b] text-white rounded px-1.5 py-0.5 transition-colors flex-shrink-0"
            >
              {a.ticker.symbol}
            </Link>
          )}

          {/* Sentiment */}
          <span className={`inline-flex items-center gap-1.5 text-xs font-semibold flex-shrink-0 ${sentimentTextColor(a.sentiment)}`}>
            <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${sentimentDot(a.sentiment)}`} />
            {sentimentLabel(a.sentiment)}
          </span>

          {/* AI badge */}
          {a.aiSummary && (
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-[#1a56db] flex-shrink-0">
              <Sparkles className="w-2.5 h-2.5" />
              AI
            </span>
          )}

          {/* Source */}
          <span className="text-[11px] text-[#9ca3af]">{a.source}</span>

          {/* Date */}
          <PubDate dateStr={a.publishedAt} />
        </div>

        {/* Body */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">

            {/* Title */}
            <p className="text-sm font-bold text-[#0f172a] leading-snug mb-1.5 line-clamp-2">
              {a.title}
            </p>

            {/* Summary */}
            {a.aiSummary && (
              <p className="text-xs text-[#4b5563] leading-relaxed mb-2.5">
                {a.aiSummary}
              </p>
            )}

            {/* Impact bar */}
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1 bg-[#f0ede8] rounded-full overflow-hidden">
                <div
                  className={`h-1 rounded-full ${impactBarColor(a.sentiment)}`}
                  style={{ width: `${(a.impactScore / 10) * 100}%` }}
                />
              </div>
              {a.url && (
                <a
                  href={a.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] text-[#1a56db] hover:text-blue-700 font-semibold flex-shrink-0"
                >
                  Baca →
                </a>
              )}
            </div>
          </div>

          {/* Impact score */}
          <div className="flex-shrink-0 text-right">
            <span className={`text-2xl font-bold leading-none tabular-nums ${impactScoreColor(a.sentiment)}`}>
              {a.impactScore.toFixed(1)}
            </span>
            <p className="text-[10px] text-[#9ca3af] mt-0.5">/10</p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── SWR fetcher ───────────────────────────────────────────────────────────────

const fetcher = (url: string) => fetch(url).then(r => r.json());

// ── Main component ────────────────────────────────────────────────────────────

export default function AGradeNews() {
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const { data: articles = [], isLoading } = useSWR<ArticleData[]>(
    '/api/high-impact-news',
    fetcher,
    {
      refreshInterval:   60_000,
      revalidateOnFocus: true,
      dedupingInterval:  30_000,
      onSuccess: () => setLastUpdated(new Date()),
    },
  );

  if (!isLoading && articles.length === 0) return null;

  const updatedLabel = lastUpdated
    ? `Diperbarui ${lastUpdated.toLocaleTimeString('id-ID', {
        hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta',
      })} WIB`
    : null;

  const marketHours = isMarketHours();

  return (
    <section>

      {/* Section header */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-[#9ca3af] mb-0.5">
            Berita Emiten
          </p>
          <h2 className="text-sm font-bold text-[#0f172a]">
            High-Impact Saham
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {marketHours && (
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse flex-shrink-0" title="Live" />
          )}
          {updatedLabel && (
            <span className="text-[10px] text-[#9ca3af] tabular-nums">{updatedLabel}</span>
          )}
          <span className="text-[11px] text-[#9ca3af]">impact ≥ 7.0 · AI enriched</span>
        </div>
      </div>

      <hr className="border-[#e5e2db] mb-4" />

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="bg-white border border-[#e5e2db] rounded-xl h-24 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {articles.map(a => <ArticleCard key={a.id} a={a} />)}
        </div>
      )}
    </section>
  );
}
