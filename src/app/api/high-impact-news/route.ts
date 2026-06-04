import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export const dynamic = 'force-dynamic';

// GET /api/high-impact-news
// Returns the top 4 high-impact stock articles for the AGradeNews component.
export async function GET() {
  const articles = await prisma.news.findMany({
    where: {
      aiSummary:   { not: null },
      impactScore: { gte: 7.0 },
      tickerId:    { not: null },
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

  return NextResponse.json(articles);
}
