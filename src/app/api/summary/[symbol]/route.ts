import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(
  _request: NextRequest,
  { params }: { params: { symbol: string } }
) {
  const symbol = params.symbol.toUpperCase();

  const ticker = await prisma.ticker.findUnique({ where: { symbol } });
  if (!ticker) {
    return NextResponse.json({ error: 'Ticker not found' }, { status: 404 });
  }

  const sentimentCounts = await prisma.news.groupBy({
    by: ['sentiment'],
    where: { tickerId: ticker.id },
    _count: true,
  });

  const distribution = { BULLISH: 0, BEARISH: 0, NEUTRAL: 0 };
  sentimentCounts.forEach((item) => {
    if (item.sentiment in distribution) {
      distribution[item.sentiment as keyof typeof distribution] = item._count;
    }
  });

  const avgImpact = await prisma.news.aggregate({
    where: { tickerId: ticker.id },
    _avg: { impactScore: true },
  });

  return NextResponse.json({
    ticker,
    sentimentDistribution: distribution,
    averageImpactScore: avgImpact._avg.impactScore ?? 5,
    newsCount: sentimentCounts.reduce((s, r) => s + r._count, 0),
  });
}
