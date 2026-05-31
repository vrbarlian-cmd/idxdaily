import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export const dynamic = 'force-dynamic';

// GET /api/news/BBRI  — convenience alias for /api/news?ticker=BBRI
export async function GET(
  _request: NextRequest,
  { params }: { params: { symbol: string } }
) {
  const symbol = params.symbol.toUpperCase();

  const tickerRow = await prisma.ticker.findUnique({ where: { symbol } });
  if (!tickerRow) {
    return NextResponse.json({ error: `Ticker ${symbol} not found` }, { status: 404 });
  }

  const mentions = await prisma.tickerMention.findMany({
    where: {
      tickerId: tickerRow.id,
      matchConfidence: { in: ['high', 'medium'] },
      article: { publishedAt: { not: null } },
    },
    orderBy: [
      { article: { publishedAt: 'desc' } },
      { article: { impactScore: 'desc' } },
    ],
    take: 50,
    select: {
      aiSummary: true,
      sentiment: true,
      impactScore: true,
      article: {
        select: {
          id: true, title: true, aiSummary: true, originalSummary: true,
          url: true, source: true, publishedAt: true, sentiment: true,
          impactScore: true, category: true, isEarlySignal: true, createdAt: true,
        },
      },
    },
  });

  // Merge mention-level fields over article-level (per-ticker summary takes priority)
  const news = mentions.map(m => ({
    ...m.article,
    aiSummary: m.aiSummary ?? m.article.aiSummary,
    sentiment: m.sentiment ?? m.article.sentiment,
    impactScore: m.impactScore ?? m.article.impactScore,
  }));

  return NextResponse.json({
    ticker: { symbol: tickerRow.symbol, name: tickerRow.name, sector: tickerRow.sector },
    count: news.length,
    news,
  });
}
