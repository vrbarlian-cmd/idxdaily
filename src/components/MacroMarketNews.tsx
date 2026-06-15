'use client';

import { Sparkles } from 'lucide-react';
import Link from 'next/link';
import { format, isToday, formatDistanceToNow } from 'date-fns';
import { id as localeId } from 'date-fns/locale';
import useSWR from 'swr';
import { useState } from 'react';
import { dedupArticles } from '@/lib/dedupArticles';

// ── Helpers ───────────────────────────────────────────────────────────────────

const SOURCE_ABBREV: Record<string, string> = {
  'Bloomberg Markets':   'Bloomberg',
  'Bloomberg Technoz':   'Technoz',
  'CNBC International':  'CNBC Intl',
  'Investing.com':       'Investing',
  'Emiten News':         'EmitenNews',
};
function formatSource(source: string): string {
  return SOURCE_ABBREV[source] ?? source;
}

function decodeHTML(str: string): string {
  return str
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

function isMarketHours(): boolean {
  const wibHour = new Date(
    new Date().toLocaleString('en-US', { timeZone: 'Asia/Jakarta' })
  ).getHours();
  return wibHour >= 9 && wibHour < 16;
}

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
function sentimentLabel(s: string) {
  if (s === 'BULLISH') return 'Bullish';
  if (s === 'BEARISH') return 'Bearish';
  return 'Netral';
}
function sentimentTextColor(s: string) {
  if (s === 'BULLISH') return 'text-emerald-700';
  if (s === 'BEARISH') return 'text-red-600';
  return 'text-amber-700';
}
function impactColor(s: string) {
  if (s === 'BULLISH') return 'text-[#1D9E75]';
  if (s === 'BEARISH') return 'text-[#E24B4A]';
  if (s === 'NEUTRAL')  return 'text-[#F59E0B]';
  return 'text-[#94A3B8]';
}
function categoryBadge(c: string | null) {
  if (c === 'MACRO')      return 'bg-blue-50 text-blue-700 border-blue-100';
  if (c === 'REGULATORY') return 'bg-violet-50 text-violet-700 border-violet-100';
  if (c === 'SECTOR')     return 'bg-sky-50 text-sky-700 border-sky-100';
  return 'bg-[#f8f7f4] text-[#9ca3af] border-[#e5e2db]';
}

// ── Types ─────────────────────────────────────────────────────────────────────

interface Article {
  id:          string;
  title:       string;
  aiSummary:   string | null;
  url:         string | null;
  source:      string;
  publishedAt: string | null;   // ISO string from JSON
  sentiment:   string;
  impactScore: number;
  category:    string | null;
  ticker:      { symbol: string } | null;
}

// ── Date badge ────────────────────────────────────────────────────────────────

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

function MacroCard({ a }: { a: Article }) {
  return (
    <div
      className={`
        relative bg-white border border-[#e5e2db] border-l-4 ${accentBar(a.sentiment)}
        ${bgTint(a.sentiment)} rounded-xl overflow-hidden
        transition-shadow duration-200 hover:shadow-sm
      `}
    >
      <div className="p-4 pl-5">

        {/* Badge row */}
        <div className="flex items-center gap-2 mb-2.5 flex-wrap">

          {/* Category */}
          {a.category && (
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold border uppercase tracking-wide flex-shrink-0 ${categoryBadge(a.category)}`}>
              {a.category}
            </span>
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

          {/* Ticker chip */}
          {a.ticker && (
            <Link
              href={`/saham/${a.ticker.symbol}`}
              className="font-mono text-[10px] font-bold bg-[#0f172a] hover:bg-[#1e293b] text-white rounded px-1.5 py-0.5 transition-colors flex-shrink-0"
            >
              {a.ticker.symbol}
            </Link>
          )}

          {/* Source + date */}
          <div className="ml-auto flex items-center gap-2 flex-shrink-0">
            <span className="text-[11px] text-[#9ca3af]">{formatSource(a.source)}</span>
            <PubDate dateStr={a.publishedAt} />
          </div>
        </div>

        {/* Title + impact score */}
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-[#0f172a] leading-snug mb-1.5 line-clamp-3 sm:line-clamp-2">
              {decodeHTML(a.title)}
            </p>
            {a.aiSummary && (
              <p className="text-xs text-[#4b5563] leading-relaxed line-clamp-3 sm:line-clamp-2">
                {a.aiSummary}
              </p>
            )}
          </div>

          {/* Impact score */}
          <div className="flex-shrink-0 text-right pt-0.5">
            <span className={`text-xl font-bold leading-none tabular-nums ${impactColor(a.sentiment)}`}>
              {a.impactScore.toFixed(1)}
            </span>
            <p className="text-[10px] text-[#9ca3af]">/10</p>
            {a.url && (
              <a
                href={a.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block mt-1 text-[11px] text-[#1a56db] hover:text-blue-700 font-semibold"
              >
                Baca →
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── SWR fetcher ───────────────────────────────────────────────────────────────

const fetcher = (url: string) => fetch(url).then(r => r.json());

// ── Main component ────────────────────────────────────────────────────────────

export default function MacroMarketNews() {
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const { data: raw = [], isLoading } = useSWR<Article[]>(
    '/api/macro-news',
    fetcher,
    {
      refreshInterval:   60_000,
      revalidateOnFocus: true,
      onSuccess: () => setLastUpdated(new Date()),
    },
  );

  // Display-level dedup: shared topic-keyword + 4-word-overlap util
  const articles = dedupArticles(raw);

  const hasFresh = articles.some(a => a.publishedAt && isToday(new Date(a.publishedAt)));

  const updatedLabel = lastUpdated
    ? `Diperbarui ${lastUpdated.toLocaleTimeString('id-ID', {
        hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta',
      })} WIB`
    : null;

  return (
    <section>

      {/* Section header */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-[#9ca3af] mb-0.5">
            Makro &amp; Pasar
          </p>
          <h2 className="text-sm font-bold text-[#0f172a]">
            Berita Makro &amp; Pasar
          </h2>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          {isMarketHours() && (
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse flex-shrink-0" title="Live" />
          )}
          {updatedLabel && (
            <span className="text-[10px] text-[#9ca3af] tabular-nums">{updatedLabel}</span>
          )}
          {!isLoading && !hasFresh && articles.length > 0 && (
            <span className="text-[11px] text-amber-700 bg-amber-50 border border-amber-100 rounded-full px-2.5 py-1 font-medium">
              Tidak ada berita makro baru hari ini
            </span>
          )}
          <span className="text-[11px] text-[#9ca3af]">IHSG · BI Rate · Global</span>
        </div>
      </div>

      <hr className="border-[#e5e2db] mb-4" />

      {/* Articles */}
      {isLoading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="bg-white border border-[#e5e2db] rounded-xl h-24 animate-pulse" />
          ))}
        </div>
      ) : articles.length > 0 ? (
        <div className="space-y-3">
          {articles.map(a => <MacroCard key={a.id} a={a} />)}
        </div>
      ) : (
        <div className="py-8 text-center text-sm text-[#9ca3af]">
          Hari ini tidak ada berita makro atau kebijakan berdampak tinggi.
          Bagian ini hanya menampilkan berita level-pasar, bukan berita emiten.
        </div>
      )}
    </section>
  );
}
