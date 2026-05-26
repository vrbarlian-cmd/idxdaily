import { Zap, Sparkles } from 'lucide-react';
import { prisma } from '@/lib/prisma';
import Link from 'next/link';
import { format, formatDistanceToNow, isToday } from 'date-fns';
import { id as localeId } from 'date-fns/locale';

// ── "Diringkas AI" badge ──────────────────────────────────────────────────────

function DiringkasAiBadge() {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold text-white flex-shrink-0"
      style={{
        background: 'linear-gradient(135deg, #7c3aed 0%, #2563eb 100%)',
        boxShadow:  '0 0 8px rgba(124,58,237,0.25)',
      }}
    >
      <Sparkles className="w-3 h-3 flex-shrink-0" />
      Diringkas AI
    </span>
  );
}

// ── Date display — prominently shows date for non-today articles ───────────────

function PubDate({ date }: { date: Date | null }) {
  if (!date) return null;
  if (isToday(date)) {
    const wib = date.toLocaleTimeString('id-ID', {
      hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta',
    });
    return <span className="text-xs text-stone-400 font-medium">{wib} WIB hari ini</span>;
  }
  const label = format(date, 'd MMM yyyy', { locale: localeId });
  const ago   = formatDistanceToNow(date, { addSuffix: true, locale: localeId });
  return (
    <span className="text-xs font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
      {label} · {ago}
    </span>
  );
}

// ── Sentiment color helpers ───────────────────────────────────────────────────

function accentBar(s: string) {
  if (s === 'BULLISH') return 'bg-emerald-500';
  if (s === 'BEARISH') return 'bg-red-500';
  return 'bg-amber-400';
}
function chipStyle(s: string) {
  if (s === 'BULLISH') return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (s === 'BEARISH') return 'bg-red-50 text-red-600 border-red-200';
  return 'bg-amber-50 text-amber-700 border-amber-200';
}
function dotColor(s: string) {
  if (s === 'BULLISH') return 'bg-emerald-500';
  if (s === 'BEARISH') return 'bg-red-500';
  return 'bg-amber-400';
}
function chipLabel(s: string) {
  if (s === 'BULLISH') return 'Bullish';
  if (s === 'BEARISH') return 'Bearish';
  return 'Netral';
}
function bgTint(s: string) {
  if (s === 'BULLISH') return 'bg-emerald-50/20';
  if (s === 'BEARISH') return 'bg-red-50/25';
  return 'bg-amber-50/20';
}
function impactBarColor(s: string) {
  if (s === 'BULLISH') return 'bg-emerald-500';
  if (s === 'BEARISH') return 'bg-red-500';
  return 'bg-amber-400';
}
function impactScoreColor(s: string) {
  if (s === 'BULLISH') return 'text-emerald-700';
  if (s === 'BEARISH') return 'text-red-600';
  return 'text-amber-700';
}

// ── Article card ─────────────────────────────────────────────────────────────

interface ArticleData {
  id:          string;
  title:       string;
  aiSummary:   string | null;
  url:         string | null;
  source:      string;
  publishedAt: Date | null;
  sentiment:   string;
  impactScore: number;
  ticker?:     { symbol: string } | null;
  category?:   string | null;
}

function ArticleCard({ a }: { a: ArticleData }) {
  return (
    <div
      className={`relative border border-stone-200 rounded-2xl p-4 pl-5 overflow-hidden shadow-sm hover:shadow-md transition-shadow duration-200 ${bgTint(a.sentiment)}`}
    >
      <div className={`absolute left-0 top-0 bottom-0 w-1 rounded-l-2xl ${accentBar(a.sentiment)}`} />

      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">

          {/* Meta row */}
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            {/* Ticker chip (stock articles only) */}
            {a.ticker && (
              <Link
                href={`/saham/${a.ticker.symbol}`}
                className="font-mono text-xs font-bold bg-stone-800 hover:bg-stone-700 text-white rounded px-2 py-0.5 transition-colors flex-shrink-0"
              >
                {a.ticker.symbol}
              </Link>
            )}

            {/* Sentiment chip */}
            <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold border flex-shrink-0 ${chipStyle(a.sentiment)}`}>
              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dotColor(a.sentiment)}`} />
              {chipLabel(a.sentiment)}
            </span>

            {/* AI badge */}
            {a.aiSummary && <DiringkasAiBadge />}

            {/* Source */}
            <span className="text-xs text-stone-500 font-medium">{a.source}</span>

            {/* Date — prominent for non-today */}
            <PubDate date={a.publishedAt} />
          </div>

          {/* Title */}
          <p className="text-sm font-bold text-stone-900 leading-snug mb-1.5 line-clamp-2">
            {a.title}
          </p>

          {/* Summary */}
          {a.aiSummary && (
            <p className="text-xs text-stone-600 leading-relaxed mb-2">
              {a.aiSummary}
            </p>
          )}

          {/* Impact bar */}
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1 bg-stone-100 rounded-full overflow-hidden">
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
                className="text-xs text-brand-600 hover:text-brand-700 font-semibold flex-shrink-0"
              >
                Baca →
              </a>
            )}
          </div>
        </div>

        {/* Impact score badge */}
        <div className="flex-shrink-0 text-right">
          <span className={`text-2xl font-bold leading-none tabular-nums ${impactScoreColor(a.sentiment)}`}>
            {a.impactScore.toFixed(1)}
          </span>
          <p className="text-xs text-stone-400 mt-0.5">/10</p>
        </div>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
// Stock-specific high-impact news only.
// Market-level macro news is handled by MacroMarketNews component (placed higher on page).

export default async function AGradeNews() {
  const stockArticles = await prisma.news.findMany({
    where: {
      aiSummary:   { not: null },
      impactScore: { gte: 7.5 },
      tickerId:    { not: null },
      // Exclude articles already shown in MacroMarketNews
      category:    { notIn: ['MACRO', 'REGULATORY'] },
    },
    orderBy: [{ publishedAt: 'desc' }, { impactScore: 'desc' }],
    take: 4,
    select: {
      id: true, title: true, aiSummary: true, url: true, source: true,
      publishedAt: true, sentiment: true, impactScore: true, category: true,
      ticker: { select: { symbol: true } },
    },
  });

  if (stockArticles.length === 0) return null;

  return (
    <section className="space-y-4">
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Zap className="w-4 h-4 text-amber-500" />
          <h2 className="text-sm font-bold text-stone-800">High-Impact Saham</h2>
          <span className="text-xs text-stone-400 bg-stone-100 rounded-full px-2 py-0.5">
            {stockArticles.length}
          </span>
        </div>
        <div className="space-y-3">
          {stockArticles.map(a => (
            <ArticleCard key={a.id} a={a} />
          ))}
        </div>
      </div>
    </section>
  );
}
