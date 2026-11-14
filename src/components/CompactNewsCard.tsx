'use client';

import { Sparkles } from 'lucide-react';
import Link from 'next/link';
import { format, formatDistanceToNow, isToday } from 'date-fns';
import { id as localeId } from 'date-fns/locale';
import { useEffect, useRef, useState } from 'react';

// Shared compact card for the homepage news sections (Berita Makro & Pasar,
// High-Impact Saham). Phone-first: headline gets the full width, the AI
// summary is clamped to 2 lines with tap-to-expand, and the impact score is a
// small chip instead of a big number column.

export interface CompactArticle {
  id:          string;
  title:       string;
  aiSummary:   string | null;
  url:         string | null;
  source:      string;
  publishedAt: string | null;   // ISO string from JSON
  sentiment:   string;
  impactScore: number;
  category?:   string | null;
  ticker?:     { symbol: string } | null;
}

function accentBar(s: string) {
  if (s === 'BULLISH') return 'border-l-emerald-500';
  if (s === 'BEARISH') return 'border-l-red-500';
  return 'border-l-amber-400';
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
function categoryBadge(c: string | null | undefined) {
  if (c === 'MACRO')      return 'bg-blue-50 text-blue-700 border-blue-100';
  if (c === 'REGULATORY') return 'bg-violet-50 text-violet-700 border-violet-100';
  if (c === 'SECTOR')     return 'bg-sky-50 text-sky-700 border-sky-100';
  return 'bg-[#f8f7f4] text-[#9ca3af] border-[#e5e2db]';
}

function decodeHTML(str: string): string {
  return str
    .replace(/&#x([0-9a-fA-F]+);/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, dec) => String.fromCharCode(parseInt(dec, 10)))
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'");
}

function PubDate({ dateStr }: { dateStr: string | null }) {
  if (!dateStr) return null;
  const date = new Date(dateStr);
  if (isToday(date)) {
    const wib = date.toLocaleTimeString('id-ID', {
      hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta',
    });
    return <span className="tabular-nums">{wib} WIB</span>;
  }
  const label = format(date, 'd MMM', { locale: localeId });
  const ago   = formatDistanceToNow(date, { addSuffix: true, locale: localeId });
  return <span className="text-amber-700 font-medium">{label} · {ago}</span>;
}

export function CompactNewsCard({ a, showCategory = false }: { a: CompactArticle; showCategory?: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const [clamped,  setClamped]  = useState(false);
  const summaryRef = useRef<HTMLParagraphElement>(null);
  const summary = a.aiSummary ?? '';

  // Only offer "Selengkapnya" when the 2-line clamp actually hides text
  // (on wide screens most summaries fit and need no button).
  useEffect(() => {
    const el = summaryRef.current;
    if (!el) return;
    const measure = () => { if (!expanded) setClamped(el.scrollHeight > el.clientHeight + 1); };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [summary, expanded]);

  return (
    <article
      className={`bg-white border border-[#e5e2db] border-l-4 ${accentBar(a.sentiment)} rounded-xl px-4 py-3 transition-shadow duration-200 hover:shadow-sm`}
    >
      {/* Meta row */}
      <div className="flex items-center gap-2 mb-1.5 min-w-0">
        {a.ticker && (
          <Link
            href={`/saham/${a.ticker.symbol}`}
            className="font-mono text-[10px] font-bold bg-[#0f172a] hover:bg-[#1e293b] text-white rounded px-1.5 py-0.5 transition-colors flex-shrink-0"
          >
            {a.ticker.symbol}
          </Link>
        )}
        {showCategory && a.category && (
          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold border uppercase tracking-wide flex-shrink-0 ${categoryBadge(a.category)}`}>
            {a.category}
          </span>
        )}
        <span className={`inline-flex items-center gap-1 text-[11px] font-semibold flex-shrink-0 ${sentimentTextColor(a.sentiment)}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${sentimentDot(a.sentiment)}`} />
          {sentimentLabel(a.sentiment)}
        </span>
        <span className="ml-auto text-[11px] text-[#9ca3af] truncate min-w-0">{a.source}</span>
      </div>

      <div className="flex gap-3">
      <div className="flex-1 min-w-0">
      {/* Headline */}
      <h3 className="text-[15px] md:text-sm font-bold text-[#0f172a] leading-snug line-clamp-2">
        {decodeHTML(a.title)}
      </h3>

      {/* AI summary — 2 lines, tap to expand */}
      {summary && (
        <div className="mt-1">
          <p ref={summaryRef} className={`text-[13px] md:text-xs text-[#4b5563] leading-relaxed ${expanded ? '' : 'line-clamp-2'}`}>
            <Sparkles className="inline w-3 h-3 text-[#1a56db] mr-1 -mt-0.5" aria-label="Ringkasan AI" />
            {summary}
          </p>
          {(clamped || expanded) && (
            <button
              onClick={() => setExpanded(v => !v)}
              className="text-[11px] font-semibold text-[#6b7280] hover:text-[#0f172a] mt-0.5 py-1"
            >
              {expanded ? 'Tutup' : 'Selengkapnya'}
            </button>
          )}
        </div>
      )}
      </div>

      {/* Impact score — big number, /10 underneath */}
      <div className="flex-shrink-0 w-11 text-right" title="Skor dampak">
        <div className={`text-2xl font-bold leading-none tabular-nums ${sentimentTextColor(a.sentiment)}`}>
          {a.impactScore.toFixed(1)}
        </div>
        <div className="text-[10px] text-[#9ca3af] mt-0.5">/10</div>
      </div>
      </div>

      {/* Footer */}
      <div className="flex items-center gap-2 mt-2 text-[11px] text-[#9ca3af]">
        <PubDate dateStr={a.publishedAt} />
        {a.url && (
          <a
            href={a.url}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto text-[12px] text-[#1a56db] hover:text-blue-700 font-semibold py-1 pl-2"
          >
            Baca →
          </a>
        )}
      </div>
    </article>
  );
}

// List with "show more": keeps the homepage short; the rest is one tap away.
export function CompactNewsList({
  articles, initial = 4, showCategory = false,
}: {
  articles: CompactArticle[];
  initial?: number;
  showCategory?: boolean;
}) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? articles : articles.slice(0, initial);
  const hidden  = articles.length - visible.length;

  return (
    <div className="space-y-2.5">
      {visible.map(a => <CompactNewsCard key={a.id} a={a} showCategory={showCategory} />)}
      {articles.length > initial && (
        <button
          onClick={() => setShowAll(v => !v)}
          className="w-full text-xs font-semibold text-[#1a56db] bg-white border border-[#e5e2db] hover:border-[#d1cdc7] rounded-xl py-2.5 transition-colors"
        >
          {showAll ? 'Tampilkan lebih sedikit' : `Tampilkan ${hidden} berita lainnya`}
        </button>
      )}
    </div>
  );
}
