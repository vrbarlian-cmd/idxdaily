import type { Metadata } from 'next';
import Link from 'next/link';
import { classify } from '@/lib/fearGreed';
import { zoneColors } from '@/lib/zoneColors';
import { getFgDays, isTradingWeekday, fmtIdDate, COMPONENT_INFO } from '@/lib/fearGreedArchive';
import { FgScoreCard, FgComponentsTable, FgDisclaimer } from '@/components/FgDayView';
import { SITE_URL } from '@/lib/tickerSeo';

export const revalidate = 300;

const TITLE = 'Fear & Greed Index IHSG Hari Ini | DailyIHSG';

export async function generateMetadata(): Promise<Metadata> {
  const days   = await getFgDays(3);
  const latest = days.find(d => !d.isBackfilled) ?? days[0];
  const description = latest
    ? `Fear & Greed Index IHSG terbaru: ${Math.round(latest.score)} (${classify(latest.score)}). ` +
      'Indikator sentimen pasar saham Indonesia dari 6 komponen: momentum & volatilitas IHSG, ' +
      'aliran asing, rupiah, sentimen berita, dan market breadth.'
    : 'Fear & Greed Index IHSG: indikator sentimen pasar saham Indonesia dari 6 komponen data pasar.';
  return {
    title: TITLE,
    description,
    alternates: { canonical: `${SITE_URL}/fear-greed` },
    openGraph: { title: TITLE, description, url: `${SITE_URL}/fear-greed`, siteName: 'DailyIHSG', locale: 'id_ID', type: 'website' },
  };
}

export default async function FearGreedPage() {
  const days   = await getFgDays(45);
  const latest = days.find(d => !d.isBackfilled) ?? days[0] ?? null;
  const prev   = latest ? days.find(d => d.date < latest.date) ?? null : null;

  const todayWib  = new Date(Date.now() + 7 * 3600_000).toISOString().slice(0, 10);
  const cutoffIso = new Date(Date.now() - 30 * 86_400_000).toISOString().slice(0, 10);
  const archive   = days.filter(d => d.date >= cutoffIso && isTradingWeekday(d.date));

  // Weights for the methodology section come from the stored row (same values
  // the calculation used); fall back to the documented defaults.
  const weightOf = (id: string) =>
    latest?.components.find(c => c.id === id)?.weight ?? COMPONENT_INFO[id]?.fallbackWeight ?? 0;

  const breadcrumbLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Beranda', item: SITE_URL },
      { '@type': 'ListItem', position: 2, name: 'Fear & Greed Index IHSG', item: `${SITE_URL}/fear-greed` },
    ],
  };

  return (
    <div className="min-h-screen bg-[#f8f7f4]">
      <main className="max-w-3xl mx-auto px-4 py-6 space-y-6">
        <nav className="flex items-center gap-1.5 text-xs text-[#9ca3af]">
          <Link href="/" className="hover:text-[#6b7280]">Beranda</Link>
          <span>/</span>
          <span className="text-[#6b7280]">Fear &amp; Greed Index</span>
        </nav>

        <header>
          <h1 className="text-2xl md:text-3xl font-bold text-[#0f172a]">Fear &amp; Greed Index IHSG</h1>
          <p className="text-sm text-[#6b7280] mt-1">
            Ukuran harian suasana hati pasar saham Indonesia, dari 0 (ketakutan ekstrem) sampai 100 (keserakahan ekstrem).
          </p>
        </header>

        {latest ? (
          <>
            <FgScoreCard
              day={latest}
              prev={prev}
              title={latest.date === todayWib ? 'Hari ini' : `Skor terbaru · ${fmtIdDate(latest.date)}`}
            />
            <section>
              <h2 className="text-base font-bold text-[#0f172a] mb-2">6 komponen hari ini</h2>
              <FgComponentsTable day={latest} />
            </section>
          </>
        ) : (
          <p className="text-sm text-[#6b7280] bg-white border border-[#e5e2db] rounded-2xl p-5">
            Data Fear &amp; Greed belum tersedia. Silakan coba lagi nanti.
          </p>
        )}

        <section className="bg-white border border-[#e5e2db] rounded-2xl p-5 space-y-3 text-sm text-[#374151] leading-relaxed">
          <h2 className="text-base font-bold text-[#0f172a]">Metodologi</h2>
          <p>
            Indeks ini menggabungkan 6 komponen. Setiap komponen diberi skor 0–100 dengan cara
            membandingkan nilai hari ini terhadap riwayatnya sendiri (peringkat persentil): skor 80
            berarti nilai hari ini lebih tinggi dari sekitar 80% hari-hari sebelumnya.
          </p>
          <ul className="space-y-2">
            {Object.entries(COMPONENT_INFO).map(([id, info]) => (
              <li key={id}>
                <span className="font-semibold text-[#0f172a]">{info.name} ({Math.round(weightOf(id) * 100)}%)</span>
                {' '}— {info.text}
              </li>
            ))}
          </ul>
          <p>
            Skor akhir adalah rata-rata berbobot dari komponen yang datanya tersedia. Agar tidak
            melompat-lompat, skor dihaluskan: 70% skor hari ini ditambah 30% skor hari sebelumnya.
          </p>
          <p>
            Kategori: di bawah 25 <b>Extreme Fear</b>, 25–44 <b>Fear</b>, 45–54 <b>Neutral</b>,
            55–74 <b>Greed</b>, 75 ke atas <b>Extreme Greed</b>.
          </p>
          <p className="text-[#6b7280]">
            Data aliran asing, aliran domestik dan market breadth berasal dari data harian Bursa Efek
            Indonesia; kurs USD/IDR dari kurs referensi harian; sentimen berita dari analisis AI atas
            berita pasar yang dikumpulkan DailyIHSG.
          </p>
        </section>

        {archive.length > 0 && (
          <section>
            <h2 className="text-base font-bold text-[#0f172a] mb-2">Arsip 30 hari</h2>
            <ul className="bg-white border border-[#e5e2db] rounded-2xl divide-y divide-[#f0ede8]">
              {archive.map(d => {
                const z = zoneColors(d.score);
                return (
                  <li key={d.date}>
                    <Link href={`/fear-greed/${d.date}`} className="flex items-center justify-between gap-3 px-4 py-2.5 hover:bg-[#fbfaf8]">
                      <span className="text-sm text-[#374151]">{fmtIdDate(d.date)}</span>
                      <span className="flex items-center gap-2">
                        <span className="text-xs text-[#6b7280]">{classify(d.score)}</span>
                        <span className="w-9 text-right font-bold tabular-nums" style={{ color: z.hex }}>{Math.round(d.score)}</span>
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        <FgDisclaimer />

        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd).replace(/</g, '\\u003c') }}
        />
      </main>
    </div>
  );
}
