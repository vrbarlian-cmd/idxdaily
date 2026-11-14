'use client';

import useSWR from 'swr';
import { useState } from 'react';
import { dedupArticles } from '@/lib/dedupArticles';
import { CompactNewsList, type CompactArticle } from '@/components/CompactNewsCard';

// ── Helpers ───────────────────────────────────────────────────────────────────

function isMarketHours(): boolean {
  const wibHour = new Date(
    new Date().toLocaleString('en-US', { timeZone: 'Asia/Jakarta' })
  ).getHours();
  return wibHour >= 9 && wibHour < 16;
}

// ── SWR fetcher ───────────────────────────────────────────────────────────────

const fetcher = (url: string) => fetch(url).then(r => r.json());

// ── Main component ────────────────────────────────────────────────────────────

export default function AGradeNews() {
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const { data: articles = [], isLoading } = useSWR<CompactArticle[]>(
    '/api/high-impact-news',
    fetcher,
    {
      refreshInterval:   60_000,
      revalidateOnFocus: true,
      dedupingInterval:  30_000,
      onSuccess: () => setLastUpdated(new Date()),
    },
  );

  const deduped = dedupArticles(articles);

  if (!isLoading && deduped.length === 0) return null;

  const updatedLabel = lastUpdated
    ? `Diperbarui ${lastUpdated.toLocaleTimeString('id-ID', {
        hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta',
      })} WIB`
    : null;

  const marketHours = isMarketHours();

  return (
    <section>

      {/* Section header */}
      <div className="flex items-end justify-between gap-3 mb-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-[#9ca3af] mb-0.5">
            Berita Emiten
          </p>
          <h2 className="text-base md:text-sm font-bold text-[#0f172a]">
            High-Impact Saham
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {marketHours && (
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse flex-shrink-0" title="Live" />
          )}
          {updatedLabel && (
            <span className="text-[10px] text-[#9ca3af] tabular-nums">{updatedLabel}</span>
          )}
          <span className="hidden md:inline text-[11px] text-[#9ca3af]">impact ≥ 7.0 · AI enriched</span>
        </div>
      </div>

      <hr className="border-[#e5e2db] mb-3" />

      {isLoading ? (
        <div className="space-y-2.5">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="bg-white border border-[#e5e2db] rounded-xl h-24 animate-pulse" />
          ))}
        </div>
      ) : (
        <CompactNewsList articles={deduped} initial={4} />
      )}
    </section>
  );
}
