import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

// Always render dynamically — this route reads query params from request.url
export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const query = searchParams.get('q')?.toUpperCase() || '';

    if (!query) {
      // Return top tickers if no query
      const tickers = await prisma.ticker.findMany({
        take: 20,
        orderBy: { symbol: 'asc' },
      });

      return NextResponse.json(tickers);
    }

    // Search by symbol or name
    const tickers = await prisma.ticker.findMany({
      where: {
        OR: [
          { symbol: { contains: query } },
          { name: { contains: query } },
        ],
      },
      take: 10,
      orderBy: { symbol: 'asc' },
    });

    return NextResponse.json(tickers);
  } catch (error) {
    console.error('Error searching tickers:', error);
    return NextResponse.json(
      { error: 'Failed to search tickers' },
      { status: 500 }
    );
  }
}
