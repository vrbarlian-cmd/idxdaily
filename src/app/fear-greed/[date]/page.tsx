import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { cache } from 'react';
import { classify } from '@/lib/fearGreed';
import { getFgDayWithPrev, isTradingWeekday, fmtIdDate } from '@/lib/fearGreedArchive';
import { FgScoreCard, FgComponentsTable, FgDisclaimer } from '@/components/FgDayView';
import { SITE_URL } from '@/lib/tickerSeo';

export const revalidate = 3600;

interface PageProps { params: { date: string } }

const load = cache((date: string) => getFgDayWithPrev(date));

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const date = params?.date ?? '';
  const data = await load(date);
  if (!data) return { title: 'Fear & Greed Index IHSG | DailyIHSG', robots: { index: false, follow: true } };
  const label = fmtIdDate(data.day.date);
  const title = `Fear & Greed Index IHSG ${label} | DailyIHSG`;
  const description =
    `Fear & Greed Index IHSG pada ${label}: ${Math.round(data.day.score)} (${classify(data.day.score)}). ` +
    'Lihat skor dan 6 komponen pembentuknya.';
  return {
    title,
    description,
    alternates: { canonical: `${SITE_URL}/fear-greed/${data.day.date}` },
    // Weekend rows are re-runs on non-trading days — reachable, not indexed.
    robots: isTradingWeekday(data.day.date) ? { index: true, follow: true } : { index: false, follow: true },
  };
}

export default async function FearGreedDayPage({ params }: PageProps) {
  const data = await load(params?.date ?? '');
  if (!data) notFound();
  const { day, prev, next } = data;

  const breadcrumbLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Beranda', item: SITE_URL },
      { '@type': 'ListItem', position: 2, name: 'Fear & Greed Index IHSG', item: `${SITE_URL}/fear-greed` },
      { '@type': 'ListItem', position: 3, name: fmtIdDate(day.date), item: `${SITE_URL}/fear-greed/${day.date}` },
    ],
  };

  return (
    <div className="min-h-screen bg-[#f8f7f4]">
      <main className="max-w-3xl mx-auto px-4 py-6 space-y-6">
        <nav className="flex items-center gap-1.5 text-xs text-[#9ca3af] flex-wrap">
          <Link href="/" className="hover:text-[#6b7280]">Beranda</Link>
          <span>/</span>
          <Link href="/fear-greed" className="hover:text-[#6b7280]">Fear &amp; Greed Index</Link>
          <span>/</span>
          <span className="text-[#6b7280]">{day.date}</span>
        </nav>

        <header>
          <h1 className="text-2xl md:text-3xl font-bold text-[#0f172a]">Fear &amp; Greed Index IHSG</h1>
          <p className="text-sm text-[#6b7280] mt-1">{fmtIdDate(day.date)}</p>
        </header>

        <FgScoreCard day={day} prev={prev} title="Skor hari itu" />

        <section>
          <h2 className="text-base font-bold text-[#0f172a] mb-2">6 komponen</h2>
          <FgComponentsTable day={day} />
        </section>

        <nav className="flex items-center justify-between gap-3 text-sm">
          {prev ? (
            <Link href={`/fear-greed/${prev.date}`} className="text-[#1a56db] hover:underline">← {prev.date}</Link>
          ) : <span />}
          <Link href="/fear-greed" className="text-[#6b7280] hover:text-[#0f172a]">Skor terbaru</Link>
          {next ? (
            <Link href={`/fear-greed/${next.date}`} className="text-[#1a56db] hover:underline">{next.date} →</Link>
          ) : <span />}
        </nav>

        <FgDisclaimer />

        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd).replace(/</g, '\\u003c') }}
        />
      </main>
    </div>
  );
}
