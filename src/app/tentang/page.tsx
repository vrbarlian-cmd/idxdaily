import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Tentang SahamDaily',
  description: 'Apa itu SahamDaily, bagaimana cara kerjanya, dan dari mana datanya.',
};

export default function TentangPage() {
  return (
    <div className="min-h-screen bg-stone-50">
      <main className="max-w-3xl mx-auto px-4 py-10 space-y-6">
        <h1 className="text-2xl font-bold text-[#0f172a]">Tentang SahamDaily</h1>

        <div className="bg-white rounded-xl border border-stone-200 p-6 space-y-4 text-sm text-stone-700 leading-relaxed">
          <h2 className="font-semibold text-base text-[#0f172a]">Apa itu SahamDaily?</h2>
          <p>
            SahamDaily adalah agregator berita dan sentimen pasar saham Indonesia. Kami mengumpulkan
            berita dari berbagai media keuangan, mengidentifikasi saham yang dibahas, lalu
            meringkasnya menggunakan kecerdasan buatan. Tujuannya satu: membantu investor ritel
            memantau pasar lebih efisien tanpa harus membaca puluhan artikel per hari.
          </p>

          <h2 className="font-semibold text-base text-[#0f172a]">Fear &amp; Greed Index</h2>
          <p>
            Indeks Fear &amp; Greed SahamDaily dihitung setiap hari dari dua komponen utama:
          </p>
          <ul className="list-disc list-inside space-y-1 pl-2">
            <li><span className="font-medium">Aliran dana asing</span> - net buy/sell investor asing di BEI (data Stockbit/RTI). Asing jual besar → Fear; asing beli besar → Greed.</li>
            <li><span className="font-medium">Aliran dana domestik</span> - selisih beli/jual investor domestik sebagai penyeimbang sinyal asing.</li>
          </ul>
          <p>
            Kedua komponen dinormalisasi ke skala 0–100 dan dibobot (asing 60%, domestik 40%).
            Skor akhir dihaluskan dengan rata-rata 3 hari untuk mengurangi noise harian.
            Skala: 0–20 Extreme Fear · 21–40 Fear · 41–60 Neutral · 61–80 Greed · 81–100 Extreme Greed.
          </p>

          <h2 className="font-semibold text-base text-[#0f172a]">Sumber Data</h2>
          <ul className="list-disc list-inside space-y-1 pl-2">
            <li>Berita: Detik Finance, CNBC Indonesia, Google News RSS</li>
            <li>Data flow asing/domestik: Stockbit, RTI Business</li>
            <li>Data harga &amp; market cap: IDX / Bursa Efek Indonesia</li>
            <li>Daftar emiten: Wikipedia IDX Composite (diperbarui berkala)</li>
          </ul>

          <h2 className="font-semibold text-base text-[#0f172a]">Label "Diringkas AI"</h2>
          <p>
            Artikel dengan label <span className="bg-stone-100 px-1 rounded font-mono text-xs">Diringkas AI</span> berarti
            teks asli artikel sudah diproses oleh model bahasa (Google Gemini) untuk menghasilkan
            ringkasan singkat, label sentimen (Bullish / Bearish / Neutral), dan skor dampak.
            Ringkasan bukan pengganti artikel asli - selalu baca sumber untuk konteks lengkap.
          </p>

          <p className="text-xs text-stone-500 border-t border-stone-100 pt-4">
            SahamDaily bukan penasihat investasi. Seluruh informasi di situs ini bersifat edukatif
            dan informatif. Keputusan investasi sepenuhnya merupakan tanggung jawab pembaca.
          </p>
        </div>
      </main>
    </div>
  );
}
