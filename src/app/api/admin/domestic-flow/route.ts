import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export const dynamic = 'force-dynamic';

// GET /api/admin/domestic-flow — last 10 entries (read-only, no secrets exposed)
// POST is intentionally absent — flow data is written via CLI only (set_domestic_flow.py)
export async function GET() {
  try {
    const rows = await prisma.$queryRaw<
      { date: Date; buy_value_bn: number; sell_value_bn: number }[]
    >`
      SELECT date, buy_value_bn, sell_value_bn
      FROM domestic_flow_daily
      ORDER BY date DESC
      LIMIT 10
    `;

    return NextResponse.json({
      ok: true,
      entries: rows.map(r => ({
        date: r.date.toISOString().slice(0, 10),
        buy_value_bn: Number(r.buy_value_bn),
        sell_value_bn: Number(r.sell_value_bn),
        net_idr_billions: Number(r.buy_value_bn) - Number(r.sell_value_bn),
      })),
    });
  } catch (err) {
    console.error('[admin/domestic-flow GET]', err);
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}
