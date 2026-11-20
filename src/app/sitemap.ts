import { MetadataRoute } from 'next';
import { INDEX_MIN_ARTICLES_30D, SITE_URL, getTickerIndexStats } from '@/lib/tickerSeo';
import { getFgDays, isTradingWeekday } from '@/lib/fearGreedArchive';

// Regenerate at most hourly (the data helpers are cached too).
export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();

  // Static pages. Canonical host is www (the bare domain 308-redirects).
  const staticPages: MetadataRoute.Sitemap = [
    { url: SITE_URL,                        lastModified: now, changeFrequency: 'always',  priority: 1   },
    { url: `${SITE_URL}/tentang`,           lastModified: now, changeFrequency: 'monthly', priority: 0.5 },
    { url: `${SITE_URL}/kebijakan-privasi`, lastModified: now, changeFrequency: 'monthly', priority: 0.3 },
    { url: `${SITE_URL}/disclaimer`,        lastModified: now, changeFrequency: 'monthly', priority: 0.3 },
  ];

  // Fear & Greed: main page + last 30 days of weekday archive pages.
  const fgDays = await getFgDays(45);
  const latestFg = fgDays.find(d => !d.isBackfilled) ?? fgDays[0];
  const cutoffIso = new Date(Date.now() - 30 * 86_400_000).toISOString().slice(0, 10);
  const fgPages: MetadataRoute.Sitemap = [
    {
      url: `${SITE_URL}/fear-greed`,
      lastModified: latestFg?.updatedAt ?? now,
      changeFrequency: 'daily',
      priority: 0.9,
    },
    ...fgDays
      .filter(d => d.date >= cutoffIso && isTradingWeekday(d.date))
      .map(d => ({
        url: `${SITE_URL}/fear-greed/${d.date}`,
        lastModified: d.updatedAt ?? new Date(`${d.date}T12:00:00Z`),
        changeFrequency: 'monthly' as const,
        priority: 0.4,
      })),
  ];

  // Ticker pages: only those with enough recent articles (others are noindex).
  // lastmod = created_at of the newest counted article, not build time.
  const stats = await getTickerIndexStats();
  const tickerPages: MetadataRoute.Sitemap = stats
    .filter(s => s.count30d >= INDEX_MIN_ARTICLES_30D)
    .sort((a, b) => a.symbol.localeCompare(b.symbol))
    .map(s => ({
      url: `${SITE_URL}/saham/${s.symbol}`,
      lastModified: s.newestAt ?? now,
      changeFrequency: 'daily' as const,
      priority: 0.7,
    }));

  return [...staticPages, ...fgPages, ...tickerPages];
}
