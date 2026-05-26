import { Globe2, Sparkles } from 'lucide-react';
import { prisma } from '@/lib/prisma';
import Link from 'next/link';
import { format, isToday, formatDistanceToNow } from 'date-fns';
import { id as localeId } from 'date-fns/locale';

// ── Helpers ───────────────────────────────────────────────────────────────────

function accentBar(s: string) {
  if (s === 'BULLISH') return 'border-l-emerald-500';
  if (s === 'BEARISH') return 'border-l-red-500';
  return 'border-l-amber-400';
}
function bgTint(s: string) {
  if (s === 'BULLISH') return 'bg-emerald-50/20';
  if (s === 'BEARISH') return 'bg-red-50/25';
  return 'bg-amber-50/15';
}
function sentimentChip(s: string) {
  if (s === 'BULLISH') return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (s === 'BEARISH') return 'bg-red-50 text-red-600 border-red-200';
  return 'bg-amber-50 text-amber-700 border-amber-200';
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
function impactColor(s: string) {
  if (s === 'BULLISH') return 'text-emerald-700';
  if (s === 'BEARISH') return 'text-red-600';
  return 'text-amber-700';
}
function categoryBadge(c: string | null) {
  if (c === 'MACRO')      return 'bg-blue-50 text-blue-700 border-blue-200';
  if (c === 'REGULATORY') return 'bg-violet-50 text-violet-700 border-violet-200';
  if (c === 'SECTOR')     return 'bg-sky-50 text-sky-700 border-sky-200';
  return 'bg-stone-50 text-stone-500 border-stone-200';
}

// ── Date badge ────────────────────────────────────────────────────────────────

function PubDate({ date }: { date: Date | null }) {
  if (!date) return null;
  if (isToday(date)) {
    const wib = date.toLocaleTimeString('id-ID', {
      hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta',
    });
    return (
      <span className="text-[11px] text-stone-400 font-medium tabular-nums">
        {wib} WIB
      </span>
    );
  }
  const label = format(date, 'd MMM', { locale: localeId });
  const ago   = formatDistanceToNow(date, { addSuffix: true, locale: localeId });
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
      {label} · {ago}
    </span>
  );
}

// ── Article card ──────────────────────────────────────────────────────────────

interface Article {
  id:          string;
  title:       string;
  aiSummary:   string | null;
  url:         string | null;
  source:      string;
  publishedAt: Date | null;
  sentiment:   string;
  impactScore: number;
  category:    string | null;
  ticker:      { symbol: string } | null;
}

function MacroCard({ a }: { a: Article }) {
  return (
    <div
      className={`
        relative bg-white border border-stone-200 border-l-4 ${accentBar(a.sentiment)}
        ${bgTint(a.sentiment)} rounded-2xl overflow-hidden
        shadow-sm hover:shadow-md transition-shadow duration-200
      `}
    >
      <div className="p-4 pl-5">
        {/* Badge row */}
        <div className="flex items-center gap-2 mb-2 flex-wrap">

          {/* Category */}
          {a.category && (
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold border uppercase tracking-wide flex-shrink-0 ${categoryBadge(a.category)}`}>
              {a.category}
            </span>
          )}

          {/* Sentiment */}
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold border flex-shrink-0 ${sentimentChip(a.sentiment)}`}>
            <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${sentimentDot(a.sentiment)}`} />
            {sentimentLabel(a.sentiment)}
          </span>

          {/* AI badge */}
          {a.aiSummary && (
            <span
              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold text-white flex-shrink-0"
              style={{ background: 'linear-gradient(135deg, #7c3aed 0%, #2563eb 100%)' }}
            >
              <Sparkles className="w-2.5 h-2.5" />
              AI
            </span>
          )}

          {/* Ticker chip (for the rare MACRO article that has a ticker) */}
          {a.ticker && (
            <Link
              href={`/saham/${a.ticker.symbol}`}
              className="font-mono text-[10px] font-bold bg-stone-700 hover:bg-stone-600 text-white rounded px-1.5 py-0.5 transition-colors flex-shrink-0"
            >
              {a.ticker.symbol}
            </Link>
          )}

          {/* Source + date — right-aligned */}
          <div className="ml-auto flex items-center gap-2 flex-shrink-0">
            <span className="text-[11px] text-stone-400">{a.source}</span>
            <PubDate date={a.publishedAt} />
          </div>
        </div>

        {/* Title + impact score side-by-side */}
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            {/* Title */}
            <p className="text-sm font-bold text-stone-900 leading-snug mb-1.5 line-clamp-2">
              {a.title}
            </p>

            {/* AI Summary */}
            {a.aiSummary && (
              <p className="text-xs text-stone-600 leading-relaxed line-clamp-2">
                {a.aiSummary}
              </p>
            )}
          </div>

          {/* Impact score */}
          <div className="flex-shrink-0 text-right pt-0.5">
            <span className={`text-xl font-bold leading-none tabular-nums ${impactColor(a.sentiment)}`}>
              {a.impactScore.toFixed(1)}
            </span>
            <p className="text-[10px] text-stone-400">/10</p>
            {a.url && (
              <a
                href={a.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block mt-1 text-[11px] text-brand-600 hover:text-brand-700 font-semibold"
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

// ── Main component ────────────────────────────────────────────────────────────

export default async function MacroMarketNews() {
  // Market-level macro news — three tiers:
  //
  // Tier 1: NULL-ticker MACRO articles, impact ≥ 7.0.
  //   This threshold filters out generic "IHSG diperkirakan" daily outlook
  //   articles (which Gemini scores 6.0–6.5) while keeping genuine market
  //   catalysts: BI rate decisions, MSCI/FTSE rebalancing, rupiah extremes,
  //   IHSG sharp moves, Fed hawkish signals, foreign flow events (impact 7–9).
  //
  // Tier 2: NULL-ticker REGULATORY articles, impact ≥ 5.5.
  //   Regulatory/policy news (export restrictions, government fiscal moves)
  //   are rarer and almost always genuinely market-wide when NULL-ticker.
  //
  // Tier 3: MACRO/REGULATORY articles WITH a ticker, impact ≥ 7.5 only.
  //   These are high-impact macro events that happen to get a primary ticker
  //   attached (e.g. a BI rate article about banking sector).
  //
  // SECTOR excluded: NULL-ticker SECTOR articles are too noisy (stock picks
  //   misclassified as market-wide). All genuine market-wide sector news
  //   (oil price, commodity policy) gets MACRO or REGULATORY instead.
  //
  // Sort: newest day first, highest impact within same day — so today's big
  //   catalyst beats today's routine update, but yesterday's news yields to
  //   today's regardless of impact.
  const articles = await prisma.news.findMany({
    where: {
      aiSummary: { not: null },
      OR: [
        {
          tickerId:    null,
          category:   'MACRO',
          impactScore: { gte: 7.0 },
        },
        {
          tickerId:    null,
          category:   'REGULATORY',
          impactScore: { gte: 5.5 },
        },
        {
          tickerId:    { not: null },
          category:   { in: ['MACRO', 'REGULATORY'] },
          impactScore: { gte: 7.5 },
        },
      ],
    },
    orderBy: [
      { publishedAt: 'desc' },
      { impactScore:  'desc' },
    ],
    take: 6,
    select: {
      id: true, title: true, aiSummary: true, url: true, source: true,
      publishedAt: true, sentiment: true, impactScore: true, category: true,
      ticker: { select: { symbol: true } },
    },
  });

  if (articles.length === 0) return null;

  const hasFresh = articles.some(a => a.publishedAt && isToday(a.publishedAt));

  return (
    <section className="bg-white border border-stone-200 rounded-2xl shadow-sm overflow-hidden">

      {/* Section header */}
      <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-stone-100">
        <div className="flex items-center gap-2">
          <Globe2 className="w-4 h-4 text-blue-500 flex-shrink-0" />
          <h2 className="text-sm font-bold text-stone-800">Berita Makro &amp; Pasar</h2>
          <span className="text-[10px] text-stone-400 bg-stone-100 rounded-full px-2 py-0.5">
            {articles.length}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {!hasFresh && (
            <span className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2 py-0.5 font-medium">
              Tidak ada berita baru hari ini
            </span>
          )}
          <span className="text-[11px] text-stone-400">IHSG · BI Rate · Global</span>
        </div>
      </div>

      {/* Articles */}
      <div className="p-4 space-y-3">
        {articles.map(a => (
          <MacroCard key={a.id} a={a} />
        ))}
      </div>
    </section>
  );
}
