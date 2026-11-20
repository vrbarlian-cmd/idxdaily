import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import Link from 'next/link';
import { Suspense, cache } from 'react';
import { prisma } from '@/lib/prisma';
import TrendingTickers from '@/components/TrendingTickers';
import TickerNewsFeed from '@/components/TickerNewsFeed';
import { dedupArticles } from '@/lib/dedupArticles';
import { buildMentionWhere } from '@/lib/mentionWhere';
import { INDEX_MIN_ARTICLES_30D, SITE_URL, getTickerIndexStats } from '@/lib/tickerSeo';

export const revalidate = 60;

interface PageProps {
  params: { ticker: string };
}

// ── SEO data (shared by generateMetadata + page via React cache) ──────────────

type Sent = 'BULLISH' | 'BEARISH' | 'NEUTRAL';
type SentCounts = Record<Sent, number>;

interface TopArticle {
  id: string; title: string; url: string | null; source: string;
  publishedAt: Date | null; impact: number; sentiment: Sent;
}

interface TickerSeo {
  ticker:          { id: string; symbol: string; name: string; sector: string | null };
  count7d:         number;
  count30d:        number;
  sent7d:          SentCounts;
  sent30d:         SentCounts;
  avgImpact7d:     number | null;
  avgImpact30d:    number | null;
  weeklyAvg30d:    number;          // count30d / 30 * 7
  newestCreatedAt: Date | null;     // newest non-SKIP article (any age)
  newestPublished: Date | null;
  top3:            TopArticle[];
  indexable:       boolean;
}

function asSent(s: string | null | undefined): Sent {
  return s === 'BULLISH' || s === 'BEARISH' ? s : 'NEUTRAL';
}

const getTickerSeo = cache(async (rawSymbol: string): Promise<TickerSeo | null> => {
  const symbol = (rawSymbol ?? '').toUpperCase();
  if (!symbol) return null;

  const ticker = await prisma.ticker.findUnique({
    where: { symbol },
    select: { id: true, symbol: true, name: true, sector: true },
  });
  if (!ticker) return null;

  const now       = Date.now();
  const cutoff30d = new Date(now - 30 * 24 * 60 * 60 * 1000);
  const cutoff7d  = new Date(now - 7  * 24 * 60 * 60 * 1000);

  const rows = await prisma.tickerMention.findMany({
    where: buildMentionWhere(ticker.id, undefined, cutoff30d, null, true),
    select: {
      sentiment: true, impactScore: true,
      article: {
        select: {
          id: true, title: true, url: true, source: true, publishedAt: true,
          createdAt: true, sentiment: true, impactScore: true,
        },
      },
    },
  }) ?? [];

  const empty = (): SentCounts => ({ BULLISH: 0, BEARISH: 0, NEUTRAL: 0 });
  const sent7d = empty(), sent30d = empty();
  let sum7 = 0, n7 = 0, sum30 = 0;
  let newestCreatedAt: Date | null = null, newestPublished: Date | null = null;
  const scored: TopArticle[] = [];

  for (const r of rows) {
    const a = r.article;
    if (!a) continue;
    const sent   = asSent(r.sentiment ?? a.sentiment);
    const impact = Number(r.impactScore ?? a.impactScore ?? 0) || 0;
    sent30d[sent]++;
    sum30 += impact;
    if (a.publishedAt && a.publishedAt >= cutoff7d) { sent7d[sent]++; sum7 += impact; n7++; }
    if (a.createdAt && (!newestCreatedAt || a.createdAt > newestCreatedAt)) newestCreatedAt = a.createdAt;
    if (a.publishedAt && (!newestPublished || a.publishedAt > newestPublished)) newestPublished = a.publishedAt;
    scored.push({ id: a.id, title: a.title, url: a.url, source: a.source, publishedAt: a.publishedAt, impact, sentiment: sent });
  }

  // No article in 30d → still show "Terakhir diperbarui" from the newest older one.
  if (!newestCreatedAt) {
    const older = await prisma.tickerMention.findFirst({
      where: buildMentionWhere(ticker.id, undefined, null, null, true),
      orderBy: { article: { createdAt: 'desc' } },
      select: { article: { select: { createdAt: true, publishedAt: true } } },
    });
    newestCreatedAt = older?.article?.createdAt ?? null;
    newestPublished = older?.article?.publishedAt ?? null;
  }

  const seen = new Set<string>();
  const top3 = scored
    .sort((x, y) => y.impact - x.impact || (y.publishedAt?.getTime() ?? 0) - (x.publishedAt?.getTime() ?? 0))
    .filter(t => (seen.has(t.id) ? false : (seen.add(t.id), true)))
    .slice(0, 3);

  const count30d = rows.length;
  return {
    ticker,
    count7d:      n7,
    count30d,
    sent7d, sent30d,
    avgImpact7d:  n7 > 0 ? sum7 / n7 : null,
    avgImpact30d: count30d > 0 ? sum30 / count30d : null,
    weeklyAvg30d: (count30d / 30) * 7,
    newestCreatedAt, newestPublished,
    top3,
    indexable:    count30d >= INDEX_MIN_ARTICLES_30D,
  };
});

function fmtWib(d: Date): string {
  return d.toLocaleString('id-ID', {
    timeZone: 'Asia/Jakarta', day: 'numeric', month: 'long', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  }) + ' WIB';
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const symbol = (params?.ticker ?? '').toUpperCase();
  const title  = `Berita & Sentimen Saham ${symbol} | DailyIHSG`;
  let seo: TickerSeo | null = null;
  try { seo = await getTickerSeo(symbol); } catch (err) {
    console.error('[saham] generateMetadata failed:', err);
  }
  if (!seo) return { title, robots: { index: false, follow: true } };

  const { ticker, count7d, sent7d, newestPublished, indexable } = seo;
  const isFresh = !!newestPublished && Date.now() - newestPublished.getTime() < 24 * 60 * 60 * 1000;
  const description = count7d > 0
    ? `${count7d} berita saham ${ticker.symbol} (${ticker.name}) dalam 7 hari terakhir: ` +
      `${sent7d.BULLISH} bullish, ${sent7d.BEARISH} bearish, ${sent7d.NEUTRAL} netral. ` +
      (isFresh ? 'Ada berita baru hari ini. ' : '') +
      'Ringkasan AI dan skor dampak di DailyIHSG.'
    : `Berita dan sentimen saham ${ticker.symbol} (${ticker.name}). ` +
      'Belum ada berita baru dalam 7 hari terakhir. Ringkasan AI dan skor dampak di DailyIHSG.';

  return {
    title,
    description,
    alternates: { canonical: `${SITE_URL}/saham/${ticker.symbol}` },
    robots: indexable ? { index: true, follow: true } : { index: false, follow: true },
    openGraph: { title, description, url: `${SITE_URL}/saham/${ticker.symbol}`, siteName: 'DailyIHSG', locale: 'id_ID', type: 'website' },
  };
}

function SentRow({ label, color, n7, n30 }: { label: string; color: string; n7: number; n30: number }) {
  return (
    <tr className="border-t border-[#f0ede8]">
      <td className="py-1.5 pr-2">
        <span className="inline-flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
          {label}
        </span>
      </td>
      <td className="py-1.5 text-right tabular-nums font-medium text-[#0f172a]">{n7}</td>
      <td className="py-1.5 text-right tabular-nums font-medium text-[#0f172a]">{n30}</td>
    </tr>
  );
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

// buildMentionWhere lives in @/lib/mentionWhere (shared with sitemap/trending).

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

  const seo = await getTickerSeo(symbol);
  if (!seo) notFound();
  const tickerRow = seo.ticker;

  // Same-sector tickers that pass the index threshold (cached stats, no extra query).
  const related = tickerRow.sector
    ? (await getTickerIndexStats())
        .filter(s => s.sector === tickerRow.sector && s.symbol !== tickerRow.symbol
                  && s.count30d >= INDEX_MIN_ARTICLES_30D)
        .sort((a, b) => b.count30d - a.count30d)
        .slice(0, 5)
    : [];

  const breadcrumbLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Beranda', item: SITE_URL },
      { '@type': 'ListItem', position: 2, name: `Saham ${tickerRow.symbol}`, item: `${SITE_URL}/saham/${tickerRow.symbol}` },
    ],
  };

  const mentionTrend =
    seo.weeklyAvg30d > 0
      ? seo.count7d >= seo.weeklyAvg30d * 1.2 ? 'lebih ramai dari biasanya'
      : seo.count7d <= seo.weeklyAvg30d * 0.8 ? 'lebih sepi dari biasanya'
      : 'sekitar rata-rata'
      : null;

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
  // Sentiment sub-label: show dominant sentiment's share of enriched articles.
  // With no enriched articles there is no dominant sentiment (previously the
  // all-zero sort picked BULLISH and showed "Bullish · 0% berita positif").
  const totalEnriched = sentCounts.BULLISH + sentCounts.BEARISH + sentCounts.NEUTRAL;
  const dominantSentiment = totalEnriched > 0
    ? Object.entries(sentCounts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? 'NEUTRAL'
    : 'NEUTRAL';
  const dominantCount = sentCounts[dominantSentiment as keyof typeof sentCounts];
  const dominantPct   = totalEnriched > 0 ? Math.round((dominantCount / totalEnriched) * 100) : 0;
  const sentimentSub  =
    totalEnriched === 0 ? 'Belum ada berita dalam 7 hari' :
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
            {seo.newestCreatedAt && (
              <p className="text-xs text-[#9ca3af] mt-2">
                Terakhir diperbarui: <time dateTime={seo.newestCreatedAt.toISOString()}>{fmtWib(seo.newestCreatedAt)}</time>
              </p>
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

          {/* Sidebar: data summary + trending tickers */}
          <div className="space-y-4 min-w-0">
            <section className="bg-white border border-[#e5e2db] rounded-xl p-4">
              <h2 className="text-sm font-bold text-[#0f172a] mb-3">Ringkasan Data {tickerRow.symbol}</h2>

              {seo.count30d === 0 ? (
                <p className="text-xs text-[#6b7280]">Belum ada berita {tickerRow.symbol} dalam 30 hari terakhir.</p>
              ) : (
                <>
                  <table className="w-full text-xs text-[#6b7280]">
                    <thead>
                      <tr className="text-[10px] uppercase tracking-wider text-[#9ca3af]">
                        <th className="text-left font-semibold pb-1">Sentimen</th>
                        <th className="text-right font-semibold pb-1">7 hari</th>
                        <th className="text-right font-semibold pb-1">30 hari</th>
                      </tr>
                    </thead>
                    <tbody>
                      <SentRow label="Bullish" color="#10b981" n7={seo.sent7d.BULLISH} n30={seo.sent30d.BULLISH} />
                      <SentRow label="Bearish" color="#ef4444" n7={seo.sent7d.BEARISH} n30={seo.sent30d.BEARISH} />
                      <SentRow label="Netral"  color="#f59e0b" n7={seo.sent7d.NEUTRAL} n30={seo.sent30d.NEUTRAL} />
                    </tbody>
                  </table>

                  <dl className="mt-3 space-y-1.5 text-xs">
                    <div className="flex justify-between gap-2">
                      <dt className="text-[#6b7280]">Rata-rata skor dampak</dt>
                      <dd className="font-medium text-[#0f172a] tabular-nums">
                        {seo.avgImpact7d != null ? seo.avgImpact7d.toFixed(1) : '—'} (7h) · {seo.avgImpact30d != null ? seo.avgImpact30d.toFixed(1) : '—'} (30h)
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt className="text-[#6b7280]">Berita 7 hari terakhir</dt>
                      <dd className="font-medium text-[#0f172a] tabular-nums">{seo.count7d}</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt className="text-[#6b7280]">Rata-rata per minggu (30 hari)</dt>
                      <dd className="font-medium text-[#0f172a] tabular-nums">{seo.weeklyAvg30d.toFixed(1)}</dd>
                    </div>
                  </dl>
                  {mentionTrend && (
                    <p className="mt-2 text-[11px] text-[#9ca3af]">Pemberitaan minggu ini {mentionTrend}.</p>
                  )}

                  {seo.top3.length > 0 && (
                    <div className="mt-4">
                      <h3 className="text-[10px] font-semibold uppercase tracking-wider text-[#9ca3af] mb-1.5">
                        Dampak tertinggi (30 hari)
                      </h3>
                      <ol className="space-y-2">
                        {seo.top3.map(t => (
                          <li key={t.id} className="text-xs leading-snug">
                            <span className="font-bold tabular-nums text-[#0f172a] mr-1">{t.impact.toFixed(1)}</span>
                            {t.url ? (
                              <a href={t.url} target="_blank" rel="noopener noreferrer nofollow" className="text-[#374151] hover:text-[#1a56db]">
                                {t.title}
                              </a>
                            ) : (
                              <span className="text-[#374151]">{t.title}</span>
                            )}
                            <span className="block text-[10px] text-[#9ca3af] mt-0.5">
                              {t.source}{t.publishedAt ? ` · ${t.publishedAt.toLocaleDateString('id-ID', { day: 'numeric', month: 'short', timeZone: 'Asia/Jakarta' })}` : ''}
                            </span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  )}
                </>
              )}

              {related.length > 0 && (
                <div className="mt-4 pt-3 border-t border-[#f0ede8]">
                  <h3 className="text-[10px] font-semibold uppercase tracking-wider text-[#9ca3af] mb-1.5">
                    Saham sektor {tickerRow.sector}
                  </h3>
                  <div className="flex flex-wrap gap-1.5">
                    {related.map(r => (
                      <Link key={r.symbol} href={`/saham/${r.symbol}`}
                        className="font-mono text-[11px] font-bold bg-[#f8f7f4] border border-[#e5e2db] hover:border-blue-300 hover:text-[#1a56db] rounded px-2 py-0.5 text-[#374151]">
                        {r.symbol}
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </section>

            <TrendingTickers currentTicker={tickerRow.symbol} />
          </div>
        </div>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd).replace(/</g, '\\u003c') }}
        />
      </main>
    </div>
  );
}
