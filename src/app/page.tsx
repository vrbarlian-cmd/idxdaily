import { computeFearGreed, getHistoricalValues } from '@/lib/fearGreed';
import FearGreedGauge      from '@/components/FearGreedGauge';
import FearGreedHistorical from '@/components/FearGreedHistorical';
import FearGreedChart      from '@/components/FearGreedChart';
import TrendingTickers     from '@/components/TrendingTickers';
import AGradeNews          from '@/components/AGradeNews';
import MacroMarketNews     from '@/components/MacroMarketNews';
import HeroSearch          from '@/components/HeroSearch';

export const dynamic = 'force-dynamic';

export default async function Home() {
  const [fgData, histData] = await Promise.all([
    computeFearGreed(7),
    getHistoricalValues(),
  ]);

  // Source of truth: stored smoothed_score from fear_greed_index (written by
  // compute_index.py). Falls back to live TypeScript computation if today's
  // DB row hasn't been written yet.
  const storedScore = histData.now.value;
  const gaugeData = storedScore !== null
    ? { ...fgData, score: storedScore, label: histData.now.label }
    : fgData;

  return (
    <div className="min-h-screen bg-stone-50">
      <HeroSearch />

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-4">

        {/* Row 1: Unified F&G editorial panel */}
        <div className="bg-white border border-[#e5e2db] rounded-2xl shadow-sm overflow-hidden">
          <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-[#e5e2db]">
            <FearGreedGauge data={gaugeData} />
            <FearGreedHistorical data={histData} />
          </div>
        </div>

        {/* Row 2: F&G vs IHSG correlation chart */}
        <FearGreedChart />

        {/* Row 3: Macro & Market News — full-width, near top, time-sensitive */}
        <MacroMarketNews />

        {/* Row 4: Trending Tickers — full width */}
        <TrendingTickers />

        {/* Row 5: High-Impact Stock News */}
        <AGradeNews />

      </main>
    </div>
  );
}
