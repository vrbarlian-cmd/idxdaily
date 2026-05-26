import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export const dynamic = 'force-dynamic';

export interface PsychologyIndexData {
  date:          string | null;  // YYYY-MM-DD, null when no data exists
  score:         number | null;  // smoothed score (displayed value)
  rawScore:      number | null;
  label:         string;
  activeComponents: number;
  hasRetailData: boolean;
  daysOfRetailData: number;
  retailScore:   number | null;
  retailRatio:   number | null;
  retailDirection: number | null;  // +1, -1, or 0
  domesticNetBn: number | null;
  domesticTotalBn: number | null;
  components:    ComponentEntry[];
}

interface ComponentEntry {
  id:        string;
  weight:    number;
  score:     number | null;
  raw_label: string | null;
  note:      string | null;
}

// GET /api/psychology-index
// Returns the most-recent row from fear_greed_psychology.
// If the table is empty, returns { score: null, hasRetailData: false, daysOfRetailData: 0 }.
export async function GET() {
  const rows = await prisma.$queryRaw<
    Array<{
      date:                       Date;
      score:                      number | null;
      raw_score:                  number | null;
      smoothed_score:             number | null;
      label:                      string;
      active_components:          number;
      components_json:            unknown;
      retail_participation_score: number | null;
      retail_participation_ratio: number | null;
      retail_direction:           number | null;
      domestic_net_bn:            number | null;
      domestic_total_bn:          number | null;
      has_retail_data:            boolean;
      days_of_retail_data:        number | null;
    }>
  >`
    SELECT
      date, score, raw_score, smoothed_score, label,
      active_components, components_json,
      retail_participation_score, retail_participation_ratio,
      retail_direction, domestic_net_bn, domestic_total_bn,
      has_retail_data, days_of_retail_data
    FROM fear_greed_psychology
    ORDER BY date DESC
    LIMIT 1
  `;

  if (!rows || rows.length === 0) {
    return NextResponse.json({
      date:             null,
      score:            null,
      rawScore:         null,
      label:            'Data Tidak Cukup',
      activeComponents: 0,
      hasRetailData:    false,
      daysOfRetailData: 0,
      retailScore:      null,
      retailRatio:      null,
      retailDirection:  null,
      domesticNetBn:    null,
      domesticTotalBn:  null,
      components:       [],
    });
  }

  const r = rows[0];
  const dateStr = r.date instanceof Date
    ? r.date.toISOString().slice(0, 10)
    : String(r.date).slice(0, 10);

  // Displayed score: smoothed_score (primary), fallback to score
  const displayScore = r.smoothed_score ?? r.score;

  // Parse components_json (stored as JSONB, comes back as object from pg)
  let components: ComponentEntry[] = [];
  if (r.components_json) {
    try {
      const raw = typeof r.components_json === 'string'
        ? JSON.parse(r.components_json)
        : r.components_json;
      components = Array.isArray(raw) ? raw : [];
    } catch {
      components = [];
    }
  }

  const data: PsychologyIndexData = {
    date:             dateStr,
    score:            displayScore !== null ? Number(displayScore) : null,
    rawScore:         r.raw_score  !== null ? Number(r.raw_score)  : null,
    label:            r.label,
    activeComponents: r.active_components,
    hasRetailData:    Boolean(r.has_retail_data),
    daysOfRetailData: r.days_of_retail_data ?? 0,
    retailScore:      r.retail_participation_score !== null ? Number(r.retail_participation_score) : null,
    retailRatio:      r.retail_participation_ratio !== null ? Number(r.retail_participation_ratio) : null,
    retailDirection:  r.retail_direction !== null ? Number(r.retail_direction) : null,
    domesticNetBn:    r.domestic_net_bn  !== null ? Number(r.domestic_net_bn)  : null,
    domesticTotalBn:  r.domestic_total_bn !== null ? Number(r.domestic_total_bn) : null,
    components,
  };

  return NextResponse.json(data);
}
