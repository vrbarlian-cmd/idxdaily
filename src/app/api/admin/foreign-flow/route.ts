import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

// GET /api/admin/foreign-flow — last 10 entries (read-only, no secrets exposed)
// POST is intentionally absent — flow data is written via CLI only (set_foreign_flow.py)
export async function GET() {
  try {
    const rows = await prisma.$queryRaw<
      { date: Date; net_idr_billions: number }[]
    >`
      SELECT date, net_idr_billions
      FROM foreign_flow_daily
      ORDER BY date DESC
      LIMIT 10
    `;

    return NextResponse.json({
      ok: true,
      entries: rows.map(r => ({
        date: r.date.toISOString().slice(0, 10),
        net_idr_billions: Number(r.net_idr_billions),
      })),
    });
  } catch (err) {
    console.error('[admin/foreign-flow GET]', err);
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}
