import { prisma } from '@/lib/prisma';

// Read-only access to the stored daily Fear & Greed rows (written by
// backend/workers/compute_index.py). Used by /fear-greed, its archive pages and
// the sitemap. Every function is defensive: bad/missing data returns [] / null.

export interface FgComponent {
  id:       string;
  label:    string;
  weight:   number | null;
  score:    number | null;
  status:   string | null;
  rawLabel: string | null;
}

export interface FgDay {
  date:         string;          // YYYY-MM-DD
  score:        number;          // smoothed_score (display value)
  label:        string;
  updatedAt:    Date | null;     // when this row was last computed
  isBackfilled: boolean;
  components:   FgComponent[];
}

type Row = {
  date: Date | string;
  smoothed_score: number | null;
  label: string | null;
  updated_at: Date | null;
  is_backfilled: boolean | null;
  components_json: unknown;
};

function toIsoDate(d: Date | string): string {
  if (d instanceof Date) return d.toISOString().slice(0, 10);
  return String(d).slice(0, 10);
}

function parseComponents(raw: unknown): FgComponent[] {
  let v: unknown = raw;
  if (typeof v === 'string') {
    try { v = JSON.parse(v); } catch { return []; }
  }
  if (!Array.isArray(v)) return [];
  return v
    .filter((c): c is Record<string, unknown> => !!c && typeof c === 'object')
    .map(c => ({
      id:       String(c.id ?? ''),
      label:    String(c.label ?? c.id ?? ''),
      weight:   typeof c.weight === 'number' ? c.weight : null,
      score:    typeof c.score === 'number' ? c.score : null,
      status:   typeof c.status === 'string' ? c.status : null,
      rawLabel: typeof c.raw_label === 'string' ? c.raw_label
              : typeof c.rawLabel === 'string' ? c.rawLabel : null,
    }))
    .filter(c => c.id);
}

function toDay(r: Row): FgDay | null {
  if (r?.smoothed_score == null || !r.date) return null;
  return {
    date:         toIsoDate(r.date),
    score:        Number(r.smoothed_score),
    label:        r.label ?? '',
    updatedAt:    r.updated_at ?? null,
    isBackfilled: !!r.is_backfilled,
    components:   parseComponents(r.components_json),
  };
}

/** Most recent rows, newest first. */
export async function getFgDays(limit = 45): Promise<FgDay[]> {
  try {
    const rows = await prisma.$queryRaw<Row[]>`
      SELECT date, smoothed_score, label, updated_at, is_backfilled, components_json
      FROM fear_greed_index
      WHERE smoothed_score IS NOT NULL
      ORDER BY date DESC
      LIMIT ${limit}
    `;
    return (rows ?? []).map(toDay).filter((d): d is FgDay => d !== null);
  } catch (err) {
    console.error('[fearGreedArchive] getFgDays failed:', err);
    return [];
  }
}

/** One day plus the row before it (for "change vs previous day"). */
export async function getFgDayWithPrev(isoDate: string): Promise<{ day: FgDay; prev: FgDay | null; next: FgDay | null } | null> {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(isoDate)) return null;
  const d = new Date(`${isoDate}T00:00:00Z`);
  if (isNaN(d.getTime()) || toIsoDate(d) !== isoDate) return null;
  try {
    const [cur, prev, next] = await Promise.all([
      prisma.$queryRaw<Row[]>`
        SELECT date, smoothed_score, label, updated_at, is_backfilled, components_json
        FROM fear_greed_index WHERE date = ${d}::date AND smoothed_score IS NOT NULL LIMIT 1`,
      prisma.$queryRaw<Row[]>`
        SELECT date, smoothed_score, label, updated_at, is_backfilled, components_json
        FROM fear_greed_index WHERE date < ${d}::date AND smoothed_score IS NOT NULL
        ORDER BY date DESC LIMIT 1`,
      prisma.$queryRaw<Row[]>`
        SELECT date, smoothed_score, label, updated_at, is_backfilled, components_json
        FROM fear_greed_index WHERE date > ${d}::date AND smoothed_score IS NOT NULL
        ORDER BY date ASC LIMIT 1`,
    ]);
    const day = cur?.[0] ? toDay(cur[0]) : null;
    if (!day) return null;
    return {
      day,
      prev: prev?.[0] ? toDay(prev[0]) : null,
      next: next?.[0] ? toDay(next[0]) : null,
    };
  } catch (err) {
    console.error('[fearGreedArchive] getFgDayWithPrev failed:', err);
    return null;
  }
}

/** Weekday rows only: weekend rows are live re-runs on non-trading days. */
export function isTradingWeekday(isoDate: string): boolean {
  const day = new Date(`${isoDate}T00:00:00Z`).getUTCDay();
  return day !== 0 && day !== 6;
}

export function fmtIdDate(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString('id-ID', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC',
  });
}

export function fmtWib(d: Date): string {
  return d.toLocaleString('id-ID', {
    timeZone: 'Asia/Jakarta', day: 'numeric', month: 'long', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  }) + ' WIB';
}

/** Plain-Bahasa explanation of each component (keyed by component id). */
export const COMPONENT_INFO: Record<string, { name: string; text: string; fallbackWeight: number }> = {
  ihsg_momentum: {
    name: 'Momentum IHSG', fallbackWeight: 0.20,
    text: 'Seberapa jauh IHSG berada di atas atau di bawah rata-rata 125 hari perdagangan. Makin jauh di atas rata-rata, makin "greed".',
  },
  ihsg_volatility: {
    name: 'Volatilitas IHSG', fallbackWeight: 0.15,
    text: 'Besarnya naik-turun harian IHSG selama 20 hari terakhir. Pasar yang bergejolak tinggi dianggap "fear".',
  },
  foreign_flow: {
    name: 'Aliran Dana Asing', fallbackWeight: 0.20,
    text: 'Total beli bersih investor asing selama 5 hari bursa terakhir. Asing banyak menjual berarti "fear".',
  },
  rupiah_stress: {
    name: 'Tekanan Rupiah', fallbackWeight: 0.15,
    text: 'Posisi kurs USD/IDR dibanding rata-rata 50 hari. Rupiah yang melemah di atas rata-ratanya berarti "fear".',
  },
  headline_sentiment: {
    name: 'Sentimen Berita', fallbackWeight: 0.20,
    text: 'Perbandingan berita positif dan negatif tentang pasar dalam 48 jam terakhir, dinilai oleh AI. Berita 24 jam terakhir diberi bobot lebih besar.',
  },
  breadth: {
    name: 'Market Breadth', fallbackWeight: 0.10,
    text: 'Persentase saham yang naik dibanding seluruh saham yang diperdagangkan hari itu. Banyak saham naik berarti "greed".',
  },
};
