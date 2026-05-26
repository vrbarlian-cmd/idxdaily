/**
 * FlowReminderBanner — server component
 *
 * Shows on the homepage:
 *   ✓  both foreign and domestic flow entered today
 *   ⚠  only one or neither entered (weekday only)
 *   —  hidden on weekends
 */

import Link from 'next/link';
import { prisma } from '@/lib/prisma';

function getWibDate(): string {
  const now = new Date();
  const wibMs = now.getTime() + 7 * 60 * 60 * 1000;
  return new Date(wibMs).toISOString().slice(0, 10);
}

function isWeekend(dateStr: string): boolean {
  const d = new Date(dateStr + 'T00:00:00Z');
  const day = d.getUTCDay();
  return day === 0 || day === 6;
}

export default async function ForeignFlowBanner() {
  const todayStr = getWibDate();

  if (isWeekend(todayStr)) return null;

  let hasForeign = false;
  let hasDomestic = false;

  try {
    const [ffRows, dfRows] = await Promise.all([
      prisma.$queryRaw<{ exists: boolean }[]>`
        SELECT EXISTS(
          SELECT 1 FROM foreign_flow_daily WHERE date = ${todayStr}::date
        ) AS exists
      `,
      prisma.$queryRaw<{ exists: boolean }[]>`
        SELECT EXISTS(
          SELECT 1 FROM domestic_flow_daily WHERE date = ${todayStr}::date
        ) AS exists
      `,
    ]);
    hasForeign = ffRows[0]?.exists ?? false;
    hasDomestic = dfRows[0]?.exists ?? false;
  } catch {
    return null;
  }

  const href = '/admin/foreign-flow';

  if (hasForeign && hasDomestic) {
    return (
      <Link
        href={href}
        className="flex items-center gap-2 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs rounded-xl px-4 py-2.5 hover:bg-emerald-100 transition-colors"
      >
        <span className="text-base leading-none">✓</span>
        <span>
          <span className="font-semibold">
            Foreign &amp; domestic flow {todayStr} sudah dimasukkan.
          </span>
          {' '}Klik untuk lihat atau koreksi.
        </span>
      </Link>
    );
  }

  const missing: string[] = [];
  if (!hasForeign) missing.push('foreign');
  if (!hasDomestic) missing.push('domestic');

  return (
    <Link
      href={href}
      className="flex items-center gap-2 bg-amber-50 border border-amber-300 text-amber-800 text-xs rounded-xl px-4 py-2.5 hover:bg-amber-100 transition-colors"
    >
      <span className="text-base leading-none">⚠</span>
      <span>
        <span className="font-semibold">
          Belum ada entri {missing.join(' &amp; ')} flow untuk hari ini ({todayStr}).
        </span>
        {' '}Klik untuk masukkan data.
      </span>
    </Link>
  );
}
