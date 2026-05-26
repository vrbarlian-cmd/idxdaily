import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

// GET /api/news?ticker=BBRI&limit=30&sentiment=BULLISH
// GET /api/news?a_grade=true            — high-impact enriched articles (no ticker required)
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const ticker = searchParams.get('ticker')?.toUpperCase();
  const limit = Math.min(parseInt(searchParams.get('limit') || '30', 10), 100);
  const sentiment = searchParams.get('sentiment')?.toUpperCase();
  const aGrade = searchParams.get('a_grade') === 'true';

  // A-grade mode: high-impact enriched articles across all tickers
  if (aGrade) {
    const cutoff = new Date();
    cutoff.setHours(cutoff.getHours() - 24);

    const news = await prisma.news.findMany({
      where: {
        aiSummary: { not: null },
        impactScore: { gte: 8.0 },
        publishedAt: { gte: cutoff },
      },
      orderBy: [{ publishedAt: 'desc' }, { impactScore: 'desc' }],
      take: limit,
      select: {
        id: true, title: true, aiSummary: true, url: true, source: true,
        publishedAt: true, sentiment: true, impactScore: true,
        category: true, isEarlySignal: true,
        ticker: { select: { symbol: true, name: true } },
      },
    });

    return NextResponse.json({ count: news.length, news });
  }

  // Ticker-specific mode
  if (!ticker) {
    return NextResponse.json(
      { error: 'ticker query param is required (or use a_grade=true)' },
      { status: 400 }
    );
  }

  const tickerRow = await prisma.ticker.findUnique({ where: { symbol: ticker } });
  if (!tickerRow) {
    return NextResponse.json({ error: `Ticker ${ticker} not found` }, { status: 404 });
  }

  const news = await prisma.news.findMany({
    where: {
      tickerId: tickerRow.id,
      ...(sentiment && ['BULLISH', 'BEARISH', 'NEUTRAL'].includes(sentiment) ? { sentiment } : {}),
    },
    orderBy: [{ publishedAt: 'desc' }, { impactScore: 'desc' }],
    take: limit,
    select: {
      id: true, title: true, aiSummary: true, originalSummary: true,
      url: true, source: true, publishedAt: true, sentiment: true,
      impactScore: true, category: true, isEarlySignal: true, createdAt: true,
    },
  });

  return NextResponse.json({
    ticker: { symbol: tickerRow.symbol, name: tickerRow.name, sector: tickerRow.sector },
    count: news.length,
    news,
  });
}
