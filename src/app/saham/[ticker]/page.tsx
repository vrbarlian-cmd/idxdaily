import { notFound } from 'next/navigation';
import Link from 'next/link';
import { Newspaper } from 'lucide-react';
import { prisma } from '@/lib/prisma';
import NewsCard from '@/components/NewsCard';
import TrendingTickers from '@/components/TrendingTickers';
import ArchiveSection from '@/components/ArchiveSection';

interface PageProps {
  params: { ticker: string };
  searchParams: { sentiment?: string };
}

function StatCard({
  label, value, sub, accent,
}: {
  label:   string;
  value:   string | number;
  sub?:    string;
  accent?: 'emerald' | 'red' | 'amber' | 'brand';
}) {
  const accentBar: Record<string, string> = {
    emerald: 'bg-emerald-500',
    red:     'bg-red-500',
    amber:   'bg-amber-400',
    brand:   'bg-brand-500',
  };
  return (
    <div className="relative bg-white border border-stone-200 rounded-2xl p-4 shadow-sm overflow-hidden">
      {accent && (
        <div className={`absolute top-0 left-0 right-0 h-0.5 ${accentBar[accent]}`} />
      )}
      <p className="text-xs text-stone-400 uppercase tracking-widest mb-1.5">{label}</p>
      <p className="text-2xl font-bold text-stone-900 leading-none">{value}</p>
      {sub && <p className="text-xs text-stone-400 mt-1.5">{sub}</p>}
    </div>
  );
}

// ── Shared mention-query helper ───────────────────────────────────────────────

function buildMentionWhere(
  tickerId: string,
  sentimentFilter: string | undefined,
  dateGte: Date | null,
  dateLt: Date | null,
  includeMacro: boolean,
) {
  const dateFilter: Record<string, unknown> = {};
  if (dateGte) dateFilter.gte = dateGte;
  if (dateLt) dateFilter.lt = dateLt;
  const hasDateFilter = Object.keys(dateFilter).length > 0;

  // INVARIANT: only show articles that have been enriched (aiSummary IS NOT NULL).
  // Unenriched articles stay hidden until enrichment completes — they must never
  // display with the DB-default NEUTRAL/5.0 placeholder values.
  return {
    tickerId,
    article: hasDateFilter
      ? { publishedAt: { ...dateFilter, not: null as null }, aiSummary: { not: null } }
      : { publishedAt: { not: null as null }, aiSummary: { not: null } },
    OR: [
      {
        matchConfidence: { in: ['high', 'medium'] },
        ...(sentimentFilter && ['BULLISH', 'BEARISH', 'NEUTRAL'].includes(sentimentFilter)
          ? {
              OR: [
                { sentiment: sentimentFilter },
                { sentiment: null, article: { sentiment: sentimentFilter } },
              ],
            }
          : {}),
      },
      ...(includeMacro ? [{ matchType: 'macro_impact' as const }] : []),
    ],
  };
}

const MENTION_SELECT = {
  aiSummary:   true,
  sentiment:   true,
  impactScore: true,
  matchType:   true,
  article: {
    select: {
      id: true, title: true, aiSummary: true, url: true, source: true,
      publishedAt: true, sentiment: true, impactScore: true,
      category: true, isEarlySignal: true,
    },
  },
} as const;

function mapMention(m: {
  aiSummary: string | null;
  sentiment: string | null;
  impactScore: number | null;
  matchType: string;
  article: {
    id: string; title: string; aiSummary: string | null; url: string | null;
    source: string; publishedAt: Date | null; sentiment: string;
    impactScore: number; category: string; isEarlySignal: boolean;
  };
}) {
  return {
    id:            m.article.id,
    title:         m.article.title,
    aiSummary:     m.aiSummary ?? m.article.aiSummary,
    url:           m.article.url,
    source:        m.article.source,
    publishedAt:   m.article.publishedAt!.toISOString(),
    sentiment:     m.sentiment ?? m.article.sentiment,
    impactScore:   m.impactScore ?? m.article.impactScore,
    category:      m.article.category,
    isEarlySignal: m.article.isEarlySignal,
    isMacroImpact: m.matchType === 'macro_impact',
  };
}

function sortMentions<T extends { matchType: string; impactScore: number | null; article: { publishedAt: Date | null; impactScore: number } }>(
  rows: T[],
): T[] {
  // Strict newest-first across all article types (including macro_impact).
  // Impact score is only used as a tiebreaker for same-second articles.
  return [...rows].sort((a, b) => {
    const timeDiff = (b.article.publishedAt?.getTime() ?? 0) - (a.article.publishedAt?.getTime() ?? 0);
    if (timeDiff !== 0) return timeDiff;
    return (b.impactScore ?? b.article.impactScore) - (a.impactScore ?? a.article.impactScore);
  });
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default async function TickerPage({ params, searchParams }: PageProps) {
  const symbol = params.ticker.toUpperCase();
  const sentimentFilter = searchParams.sentiment?.toUpperCase();

  const tickerRow = await prisma.ticker.findUnique({
    where: { symbol },
    select: { id: true, symbol: true, name: true, sector: true },
  });

  if (!tickerRow) notFound();

  // Date boundaries
  const now       = new Date();
  const cutoff30d = new Date(now); cutoff30d.setDate(now.getDate() - 30);
  const cutoff7d  = new Date(now); cutoff7d.setDate(now.getDate() - 7);

  // ── Stats: 7-day window ───────────────────────────────────────────────────
  const allMentions7d = await prisma.tickerMention.findMany({
    where: {
      tickerId: tickerRow.id,
      OR: [
        { matchConfidence: { in: ['high', 'medium'] } },
        { matchType: 'macro_impact' },
      ],
      article: { publishedAt: { gte: cutoff7d } },
    },
    select: {
      sentiment: true, impactScore: true, aiSummary: true, matchType: true,
      article: { select: { sentiment: true, impactScore: true, aiSummary: true } },
    },
  });

  const articleCount   = allMentions7d.length;
  const enrichedCount  = allMentions7d.filter(m => m.aiSummary || m.article.aiSummary).length;
  const aGradeCount    = allMentions7d.filter(m => {
    const impact = m.impactScore ?? m.article.impactScore;
    return impact >= 7.0 && (m.aiSummary || m.article.aiSummary);
  }).length;

  const sentCounts = { BULLISH: 0, BEARISH: 0, NEUTRAL: 0 };
  for (const m of allMentions7d) {
    // Only count enriched articles in sentiment distribution — unenriched ones
    // have NULL mention fields that fall back to the DB default 'NEUTRAL',
    // which would inflate the NEUTRAL count and give a false dominant sentiment.
    if (!m.aiSummary && !m.article.aiSummary) continue;
    const sent = (m.sentiment ?? m.article.sentiment) as keyof typeof sentCounts;
    if (sent in sentCounts) sentCounts[sent]++;
  }
  const dominantSentiment = Object.entries(sentCounts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? 'NEUTRAL';
  const sentimentChipStyle =
    dominantSentiment === 'BULLISH' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
    dominantSentiment === 'BEARISH' ? 'bg-red-50 text-red-600 border-red-200' :
    'bg-amber-50 text-amber-700 border-amber-200';
  const enrichPct = articleCount > 0 ? Math.round((enrichedCount / articleCount) * 100) : 0;

  // ── "Berita Terbaru" — last 30 days (live feed) ───────────────────────────
  const recentRaw = await prisma.tickerMention.findMany({
    where: buildMentionWhere(tickerRow.id, sentimentFilter, cutoff30d, null, true),
    orderBy: { article: { publishedAt: 'desc' } },
    take: 50,
    select: MENTION_SELECT,
  });

  const recentNews = sortMentions(recentRaw)
    .filter(m => !sentimentFilter || m.matchType === 'macro_impact'
      || (m.sentiment ?? m.article.sentiment) === sentimentFilter)
    .map(mapMention);

  // ── "Arsip" — older than 30 days (clearly labeled, collapsible) ───────────
  // Only fetch archive when recent news is sparse (< 5 items after filtering)
  // so we don't add clutter when there's plenty of recent news.
  const ARCHIVE_THRESHOLD = 5;
  const archiveItems = recentNews.length < ARCHIVE_THRESHOLD
    ? await prisma.tickerMention.findMany({
        where: buildMentionWhere(tickerRow.id, sentimentFilter, null, cutoff30d, false),
        orderBy: { article: { publishedAt: 'desc' } },
        take: 20,
        select: MENTION_SELECT,
      }).then(rows =>
          sortMentions(rows)
            .filter(m => !sentimentFilter || (m.sentiment ?? m.article.sentiment) === sentimentFilter)
            .map(mapMention)
      )
    : [];

  const sentiments = ['ALL', 'BULLISH', 'BEARISH', 'NEUTRAL'] as const;

  return (
    <div className="min-h-screen bg-stone-50">
      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-1.5 text-xs text-stone-400">
          <Link href="/" className="hover:text-stone-600 transition-colors">Beranda</Link>
          <span>/</span>
          <span>Saham</span>
          <span>/</span>
          <span className="font-mono font-medium text-stone-600">{tickerRow.symbol}</span>
        </nav>

        {/* Ticker header */}
        <div className="flex items-start gap-4 flex-wrap">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="font-mono text-3xl font-bold text-stone-900">{tickerRow.symbol}</h1>
              <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium border ${sentimentChipStyle}`}>
                {dominantSentiment.charAt(0) + dominantSentiment.slice(1).toLowerCase()}
              </span>
            </div>
            <p className="text-stone-500 mt-1">{tickerRow.name}</p>
            {tickerRow.sector && (
              <span className="inline-block mt-2 px-2.5 py-0.5 text-xs bg-stone-100 border border-stone-200 rounded text-stone-500">
                {tickerRow.sector}
              </span>
            )}
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard
            label="Sentimen 7d"
            value={dominantSentiment.charAt(0) + dominantSentiment.slice(1).toLowerCase()}
            accent={dominantSentiment === 'BULLISH' ? 'emerald' : dominantSentiment === 'BEARISH' ? 'red' : 'amber'}
          />
          <StatCard label="Artikel 7d" value={articleCount} />
          <StatCard label="High-Impact" value={aGradeCount} sub="impact ≥ 7.0 & enriched" accent={aGradeCount > 0 ? 'amber' : undefined} />
          <StatCard label="Enriched" value={`${enrichPct}%`} sub={`${enrichedCount} of ${articleCount}`} />
        </div>

        {/* Content: articles + sidebar */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Article list */}
          <div className="md:col-span-2 space-y-4">

            {/* ── Berita Terbaru (30d live feed) ── */}
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <p className="text-sm text-stone-700 font-semibold">Berita Terbaru</p>
                <p className="text-xs text-stone-400">30 hari terakhir · {recentNews.length} artikel</p>
              </div>
              {/* Sentiment filter */}
              <div className="flex flex-wrap gap-1">
                {sentiments.map((s) => {
                  const isActive = s === 'ALL' ? !sentimentFilter : sentimentFilter === s;
                  const href = s === 'ALL'
                    ? `/saham/${tickerRow.symbol}`
                    : `/saham/${tickerRow.symbol}?sentiment=${s}`;
                  return (
                    <Link
                      key={s}
                      href={href}
                      className={`px-3 py-1 text-xs rounded-full border transition-all font-medium ${
                        isActive
                          ? s === 'BULLISH' ? 'bg-emerald-50 border-emerald-300 text-emerald-700 shadow-sm'
                          : s === 'BEARISH' ? 'bg-red-50 border-red-300 text-red-600 shadow-sm'
                          : s === 'NEUTRAL' ? 'bg-amber-50 border-amber-300 text-amber-700 shadow-sm'
                          : 'bg-brand-50 border-brand-300 text-brand-700 shadow-sm'
                          : 'bg-white border-stone-200 text-stone-500 hover:border-stone-300 hover:bg-stone-50'
                      }`}
                    >
                      {s}
                    </Link>
                  );
                })}
              </div>
            </div>

            {recentNews.length === 0 ? (
              <div className="bg-white border border-stone-200 rounded-xl p-8 text-center space-y-3">
                <div className="flex justify-center">
                  <Newspaper className="w-8 h-8 text-stone-300" />
                </div>
                <p className="text-stone-700 font-medium text-sm">
                  {sentimentFilter
                    ? `Tidak ada berita ${sentimentFilter.toLowerCase()} untuk ${tickerRow.symbol} dalam 30 hari terakhir`
                    : `Belum ada berita terbaru untuk ${tickerRow.symbol} dalam 30 hari terakhir`
                  }
                </p>
                <p className="text-stone-400 text-xs leading-relaxed max-w-xs mx-auto">
                  {sentimentFilter
                    ? 'Coba hapus filter sentimen, atau kembali lagi nanti.'
                    : tickerRow.sector
                      ? `${tickerRow.name} belum muncul di sumber berita kami. Cek arsip di bawah untuk berita lama, atau lihat konteks makro sektor ${tickerRow.sector} di beranda.`
                      : `${tickerRow.name} belum muncul di sumber berita yang kami pantau. Kami terus menambah cakupan sumber berita secara berkala.`
                  }
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {recentNews.map((item) => (
                  <NewsCard key={item.id} news={item} isMacroImpact={item.isMacroImpact} />
                ))}
              </div>
            )}

            {/* ── Arsip (collapsible, older than 30d, clearly labeled) ── */}
            {/* Only shown when recent news is sparse AND we found archive items */}
            {archiveItems.length > 0 && (
              <ArchiveSection
                items={archiveItems}
                symbol={tickerRow.symbol}
                autoExpand={recentNews.length === 0}
              />
            )}
          </div>

          {/* Sidebar: trending tickers */}
          <div className="space-y-4">
            <TrendingTickers currentTicker={tickerRow.symbol} />
          </div>
        </div>
      </main>
    </div>
  );
}
