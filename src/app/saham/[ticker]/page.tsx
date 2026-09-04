import { notFound } from 'next/navigation';
import Link from 'next/link';
import { Suspense } from 'react';
import { prisma } from '@/lib/prisma';
import TrendingTickers from '@/components/TrendingTickers';
import TickerNewsFeed from '@/components/TickerNewsFeed';
import { dedupArticles } from '@/lib/dedupArticles';

export const revalidate = 60;

interface PageProps {
  params: { ticker: string };
}

function StatCard({
  label, value, sub, accentColor,
}: {
  label:        string;
  value:        string | number;
  sub?:         string;
  accentColor?: string;
}) {
  return (
    <div className="relative flex flex-col bg-white border border-[#e5e2db] rounded-xl p-4 overflow-hidden">
      {accentColor && (
        <div className="absolute top-0 left-0 right-0 h-[3px]" style={{ backgroundColor: accentColor }} />
      )}
      <p className="text-[11px] text-[#9ca3af] uppercase tracking-widest mb-2">{label}</p>
      <p className="text-[22px] font-medium text-[#0f172a] leading-none">{value}</p>
      {sub && <p className="text-[12px] text-[#9ca3af] mt-2 leading-snug">{sub}</p>}
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

  const validSentiment =
    !!sentimentFilter && ['BULLISH', 'BEARISH', 'NEUTRAL'].includes(sentimentFilter);

  // Match-type branch: high/medium ticker matches OR (optionally) macro-impact mentions.
  const matchTypeOr: Record<string, unknown>[] = [
    { matchConfidence: { in: ['high', 'medium'] } },
    ...(includeMacro ? [{ matchType: 'macro_impact' as const }] : []),
  ];

  // Sentiment branch — applied at the TOP level (AND) so it constrains BOTH
  // ticker-match AND macro-impact rows. Previously it lived only inside the
  // high/medium branch, so macro-impact mentions of any sentiment leaked through
  // (e.g. Bearish macro articles appearing under the Neutral filter). Falls back
  // to article.sentiment when the mention's own sentiment is null.
  const sentimentAnd = validSentiment
    ? [{
        OR: [
          { sentiment: sentimentFilter },
          { sentiment: null, article: { sentiment: sentimentFilter } },
        ],
      }]
    : [];

  // INVARIANT: only show articles that have been enriched (aiSummary IS NOT NULL).
  // Unenriched articles stay hidden until enrichment completes — they must never
  // display with the DB-default NEUTRAL/5.0 placeholder values.
  //
  // INVARIANT: never show category='SKIP' articles. enrich.py's relevance
  // pre-filter sets category=SKIP *and* a non-null placeholder aiSummary
  // ("[filtered: not market relevant]") for articles it judges irrelevant —
  // that placeholder passes the aiSummary-not-null check above, so this
  // separate category exclusion is required or SKIP articles leak through.
  return {
    tickerId,
    article: hasDateFilter
      ? { publishedAt: { ...dateFilter, not: null as null }, aiSummary: { not: null }, category: { not: 'SKIP' } }
      : { publishedAt: { not: null as null }, aiSummary: { not: null }, category: { not: 'SKIP' } },
    AND: [
      { OR: matchTypeOr },
      ...sentimentAnd,
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

export default async function TickerPage({ params }: PageProps) {
  const symbol = params.ticker.toUpperCase();

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
      article: { publishedAt: { gte: cutoff7d }, category: { not: 'SKIP' } },
    },
    select: {
      sentiment: true, impactScore: true, aiSummary: true, matchType: true,
      article: { select: { sentiment: true, impactScore: true, aiSummary: true, source: true } },
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

  // Sentiment sub-label: show dominant sentiment's share of enriched articles
  const totalEnriched = sentCounts.BULLISH + sentCounts.BEARISH + sentCounts.NEUTRAL;
  const dominantCount = sentCounts[dominantSentiment as keyof typeof sentCounts];
  const dominantPct   = totalEnriched > 0 ? Math.round((dominantCount / totalEnriched) * 100) : 0;
  const sentimentSub  =
    dominantSentiment === 'BULLISH' ? `${dominantPct}% berita positif dominan` :
    dominantSentiment === 'BEARISH' ? `${dominantPct}% berita negatif dominan` :
    `${dominantPct}% berita netral`;

  // Distinct source count in the 7d window
  const sourceCount = new Set(allMentions7d.map(m => m.article.source)).size;

  // Enriched sub-label
  const enrichSub = enrichedCount === articleCount
    ? 'Semua berita sudah diringkas'
    : `${articleCount - enrichedCount} berita belum dianalisis`;

  const sentimentChipStyle =
    dominantSentiment === 'BULLISH' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
    dominantSentiment === 'BEARISH' ? 'bg-red-50 text-red-600 border-red-200' :
    'bg-amber-50 text-amber-700 border-amber-200';

  // ── "Berita Terbaru" — last 30 days (live feed) ───────────────────────────
  // Always fetched unfiltered (no sentiment param) so this query — and the
  // whole route — stays cacheable via ISR (`revalidate` above). Sentiment
  // filtering happens client-side in TickerNewsFeed instead.
  const recentRaw = await prisma.tickerMention.findMany({
    where: buildMentionWhere(tickerRow.id, undefined, cutoff30d, null, true),
    orderBy: { article: { publishedAt: 'desc' } },
    take: 50,
    select: MENTION_SELECT,
  });

  const recentNews = dedupArticles(sortMentions(recentRaw).map(mapMention));

  // ── "Arsip" — older than 30 days (clearly labeled, collapsible) ───────────
  // Only fetch archive when recent news is sparse (< 5 items) so we don't add
  // clutter when there's plenty of recent news.
  const ARCHIVE_THRESHOLD = 5;
  const archiveItems = recentNews.length < ARCHIVE_THRESHOLD
    ? await prisma.tickerMention.findMany({
        where: buildMentionWhere(tickerRow.id, undefined, null, cutoff30d, false),
        orderBy: { article: { publishedAt: 'desc' } },
        take: 20,
        select: MENTION_SELECT,
      }).then(rows => dedupArticles(sortMentions(rows).map(mapMention)))
    : [];

  return (
    <div className="min-h-screen bg-[#f8f7f4]">
      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-1.5 text-xs text-[#9ca3af]">
          <Link href="/" className="hover:text-[#6b7280] transition-colors">Beranda</Link>
          <span>/</span>
          <span>Saham</span>
          <span>/</span>
          <span className="font-mono font-medium text-[#6b7280]">{tickerRow.symbol}</span>
        </nav>

        {/* Ticker header */}
        <div className="flex items-start gap-4 flex-wrap">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="font-mono text-3xl font-bold text-[#0f172a]">{tickerRow.symbol}</h1>
              <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium border ${sentimentChipStyle}`}>
                {dominantSentiment.charAt(0) + dominantSentiment.slice(1).toLowerCase()}
              </span>
            </div>
            <p className="text-[#6b7280] mt-1">{tickerRow.name}</p>
            {tickerRow.sector && (
              <span className="inline-block mt-2 px-2.5 py-0.5 text-xs bg-[#f8f7f4] border border-[#e5e2db] rounded text-[#6b7280]">
                {tickerRow.sector}
              </span>
            )}
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 items-stretch">
          <StatCard
            label="SENTIMEN 7 HARI"
            value={dominantSentiment.charAt(0) + dominantSentiment.slice(1).toLowerCase()}
            sub={sentimentSub}
            accentColor={
              dominantSentiment === 'BULLISH' ? '#1D9E75' :
              dominantSentiment === 'BEARISH' ? '#E24B4A' :
              '#9ca3af'
            }
          />
          <StatCard
            label="TOTAL BERITA"
            value={articleCount}
            sub={`dari ${sourceCount} sumber berbeda`}
            accentColor="#378ADD"
          />
          <StatCard
            label="BERITA PENTING"
            value={`${aGradeCount} dari ${articleCount}`}
            sub="Berpotensi gerakkan harga saham"
            accentColor="#EF9F27"
          />
          <StatCard
            label="DIANALISIS AI"
            value={`${enrichedCount}/${articleCount}`}
            sub={enrichSub}
            accentColor="#1D9E75"
          />
        </div>

        {/* Content: articles + sidebar */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Article list */}
          <div className="md:col-span-2 space-y-4">
            <Suspense fallback={null}>
              <TickerNewsFeed
                symbol={tickerRow.symbol}
                tickerName={tickerRow.name}
                sector={tickerRow.sector}
                allRecentNews={recentNews}
                allArchiveItems={archiveItems}
              />
            </Suspense>
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
