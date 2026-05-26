import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export const dynamic = 'force-dynamic';

// Divergence threshold: p60 of |foreign net| = ~1,017 Rp bn → rounded to 1,000
const DIVERGENCE_THRESHOLD_BN = 1000;

function getWibDate(): string {
  const now = new Date();
  const wibMs = now.getTime() + 7 * 60 * 60 * 1000;
  return new Date(wibMs).toISOString().slice(0, 10);
}

export type DivergenceSignal =
  | 'optimisme_retail'    // locals buying, foreigners selling → "Optimisme Retail / Hati-hati"
  | 'ketakutan_retail'    // locals selling, foreigners buying → "Ketakutan Retail / Peluang"
  | 'sejalan';            // both moving same direction, or flows too small to be notable

export interface DivergenceResult {
  date: string;
  foreign_net_bn: number;
  domestic_net_bn: number;
  signal: DivergenceSignal;
  label: string;
  description: string;
  notable: boolean;             // true only when both flows exceed threshold
  has_domestic_data: boolean;   // false → widget should be hidden
}

// GET /api/divergence — today's divergence signal (WIB)
export async function GET() {
  const todayStr = getWibDate();
  try {
    // Foreign flow for today
    const ffRows = await prisma.$queryRaw<{ net_idr_billions: number }[]>`
      SELECT net_idr_billions::float8 AS net_idr_billions
      FROM foreign_flow_daily
      WHERE date = ${todayStr}::date
    `;

    // Domestic flow for today
    const dfRows = await prisma.$queryRaw<{ buy_value_bn: number; sell_value_bn: number }[]>`
      SELECT buy_value_bn::float8 AS buy_value_bn,
             sell_value_bn::float8 AS sell_value_bn
      FROM domestic_flow_daily
      WHERE date = ${todayStr}::date
    `;

    if (dfRows.length === 0) {
      // No domestic data entered yet — widget should be hidden
      return NextResponse.json({
        date: todayStr,
        has_domestic_data: false,
        signal: 'sejalan',
        label: 'Sejalan / Netral',
        description: 'Data domestik belum tersedia.',
        notable: false,
        foreign_net_bn: ffRows.length > 0 ? Number(ffRows[0].net_idr_billions) : null,
        domestic_net_bn: null,
      });
    }

    const foreignNet = ffRows.length > 0 ? Number(ffRows[0].net_idr_billions) : 0;
    const domesticNet = Number(dfRows[0].buy_value_bn) - Number(dfRows[0].sell_value_bn);

    const absForeign = Math.abs(foreignNet);
    const absDomestic = Math.abs(domesticNet);
    const bothLarge = absForeign >= DIVERGENCE_THRESHOLD_BN && absDomestic >= DIVERGENCE_THRESHOLD_BN;

    let signal: DivergenceSignal = 'sejalan';
    let label = 'Sejalan / Netral';
    let description = 'Tidak ada divergensi signifikan antara asing dan domestik hari ini.';
    let notable = false;

    if (bothLarge) {
      // Foreigners selling (net < 0), locals net buying (net > 0)
      if (foreignNet < 0 && domesticNet > 0) {
        signal = 'optimisme_retail';
        label = 'Optimisme Retail / Hati-hati';
        description =
          `Asing net jual ${Math.abs(foreignNet).toLocaleString('id-ID', { maximumFractionDigits: 0 })} Rp miliar, ` +
          `domestik net beli ${domesticNet.toLocaleString('id-ID', { maximumFractionDigits: 0 })} Rp miliar. ` +
          `Retail menyerap tekanan jual asing — sinyal sentimen kontrarian.`;
        notable = true;
      }
      // Foreigners buying (net > 0), locals net selling (net < 0)
      else if (foreignNet > 0 && domesticNet < 0) {
        signal = 'ketakutan_retail';
        label = 'Ketakutan Retail / Peluang';
        description =
          `Asing net beli ${foreignNet.toLocaleString('id-ID', { maximumFractionDigits: 0 })} Rp miliar, ` +
          `domestik net jual ${Math.abs(domesticNet).toLocaleString('id-ID', { maximumFractionDigits: 0 })} Rp miliar. ` +
          `Retail panik saat asing akumulasi — sinyal sentimen kontrarian.`;
        notable = true;
      }
      // Both same direction but both large — worth noting as "sejalan besar"
      else {
        label = 'Sejalan / Netral';
        description = 'Asing dan domestik bergerak searah hari ini.';
      }
    }

    const result: DivergenceResult = {
      date: todayStr,
      has_domestic_data: true,
      foreign_net_bn: foreignNet,
      domestic_net_bn: domesticNet,
      signal,
      label,
      description,
      notable,
    };

    return NextResponse.json(result);
  } catch (err) {
    console.error('[/api/divergence]', err);
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}
