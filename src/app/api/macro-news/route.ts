import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export const dynamic = 'force-dynamic';

// ── Sources & filters (mirror MacroMarketNews logic) ─────────────────────────

const GLOBAL_SOURCES = [
  'Bloomberg Markets', 'CNBC International', 'Investing.com', 'Federal Reserve',
];

const MACRO_ACRONYMS = new Set([
  'BI', 'OJK', 'BEI', 'LPS', 'KSSK',
  'IHSG', 'LQ45', 'IDX', 'IDR', 'USD', 'EUR', 'JPY', 'CNY', 'SGD',
  'US', 'EU', 'UK', 'IMF', 'WTO', 'OPEC', 'G20', 'G7',
  'Fed', 'ECB', 'BOJ', 'RBI',
  'MSCI', 'FTSE', 'DJIA', 'SPX', 'DXY',
  'GDP', 'PMI', 'CPI', 'PPI', 'SBN', 'ETF', 'IPO',
  'APBN', 'APBD', 'PPN', 'PPh', 'BUMN', 'PNBP',
]);

function looksCompanySpecific(title: string): boolean {
  if (/^saham[\s-]/i.test(title)) return true;
  if (/\bemiten\s+[A-Z]{2,5}\b/i.test(title)) return true;
  if (/\bdividen\b/i.test(title)) return true;
  if (/^(laba|rugi|pendapatan)\s+[A-Z]{2,5}\b/i.test(title)) return true;
  const leadWord = title.match(/^([A-Z]{2,5})(?=[\s:])/)?.[1];
  if (leadWord && !MACRO_ACRONYMS.has(leadWord)) return true;
  return false;
}

function dedupSimilarHeadlines<T extends { title: string }>(articles: T[]): T[] {
  const kept: T[] = [];
  for (const article of articles) {
    const words = new Set(
      article.title.toLowerCase().split(/\s+/).filter(w => w.length > 3)
    );
    const similarCount = kept.filter(k => {
      const kWords = new Set(
        k.title.toLowerCase().split(/\s+/).filter(w => w.length > 3)
      );
      return Array.from(words).filter(w => kWords.has(w)).length >= 4;
    }).length;
    if (similarCount < 2) kept.push(article);
  }
  return kept;
}

// ── GET /api/macro-news ───────────────────────────────────────────────────────

export async function GET() {
  const raw = await prisma.news.findMany({
    where: {
      aiSummary: { not: null },
      tickerId:  null,
      OR: [
        { category: 'MACRO',      impactScore: { gte: 5.5 }, source: { notIn: GLOBAL_SOURCES } },
        { category: 'REGULATORY', impactScore: { gte: 5.5 }, source: { notIn: GLOBAL_SOURCES } },
        { category: 'SECTOR',     impactScore: { gte: 7.0 }, source: { notIn: GLOBAL_SOURCES } },
        { source: { in: GLOBAL_SOURCES }, aiSummary: { not: null }, impactScore: { gte: 4.5 } },
      ],
    },
    orderBy: [{ publishedAt: 'desc' }, { impactScore: 'desc' }],
    take: 12,
    select: {
      id: true, title: true, aiSummary: true, url: true, source: true,
      publishedAt: true, sentiment: true, impactScore: true, category: true,
      ticker: { select: { symbol: true } },
    },
  });

  const articles = dedupSimilarHeadlines(
    raw.filter(a => !looksCompanySpecific(a.title))
  ).slice(0, 6);

  return NextResponse.json(articles);
}
