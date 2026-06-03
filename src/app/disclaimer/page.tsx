import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Disclaimer — IDXDaily',
  description: 'Disclaimer IDXDaily: informasi di situs ini bukan saran investasi.',
};

export default function DisclaimerPage() {
  return (
    <div className="min-h-screen bg-stone-50">
      <main className="max-w-3xl mx-auto px-4 py-10 space-y-6">
        <h1 className="text-2xl font-bold text-[#0f172a]">Disclaimer</h1>
        <p className="text-xs text-stone-500">Terakhir diperbarui: Juni 2026</p>

        <div className="bg-white rounded-xl border border-stone-200 p-6 space-y-5 text-sm text-stone-700 leading-relaxed">

          <section className="space-y-2">
            <h2 className="font-semibold text-base text-[#0f172a]">Bukan Saran Investasi</h2>
            <p>
              Seluruh konten yang tersedia di IDXDaily — termasuk berita, ringkasan AI, indeks
              Fear &amp; Greed, skor sentimen, dan analisis data pasar — bersifat <strong>informatif
              dan edukatif semata</strong>. Konten ini <strong>bukan</strong> merupakan saran
              investasi, rekomendasi beli atau jual efek, atau nasihat keuangan dalam bentuk
              apapun.
            </p>
            <p>
              IDXDaily bukan perusahaan efek, manajer investasi, atau penasihat keuangan yang
              terdaftar di Otoritas Jasa Keuangan (OJK). Kami tidak memiliki izin untuk memberikan
              rekomendasi investasi.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-semibold text-base text-[#0f172a]">Tanggung Jawab Investor</h2>
            <p>
              Setiap keputusan investasi yang Anda buat sepenuhnya merupakan tanggung jawab Anda
              sendiri. Investasi di pasar modal mengandung risiko, termasuk risiko kehilangan
              sebagian atau seluruh modal. Pastikan Anda memahami risiko tersebut sebelum
              berinvestasi, dan konsultasikan dengan penasihat keuangan berlisensi jika diperlukan.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-semibold text-base text-[#0f172a]">Akurasi Data</h2>
            <p>
              IDXDaily mengambil data dari sumber pihak ketiga (media berita, platform data pasar,
              dan feed publik). Kami berupaya menampilkan informasi yang akurat dan terkini, namun
              tidak dapat menjamin keakuratan, kelengkapan, atau ketepatan waktu data tersebut.
              Jangan gunakan data dari IDXDaily sebagai satu-satunya sumber untuk keputusan
              keuangan.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-semibold text-base text-[#0f172a]">Ringkasan AI</h2>
            <p>
              Artikel yang ditandai &ldquo;Diringkas AI&rdquo; diproses menggunakan model bahasa
              kecerdasan buatan. Ringkasan tersebut mungkin mengandung ketidakakuratan atau
              nuansa yang hilang dari artikel asli. Selalu baca artikel sumber sebelum mengambil
              keputusan berdasarkan informasi tersebut. Label sentimen (Bullish/Bearish/Neutral)
              dihasilkan secara otomatis dan bukan merupakan rekomendasi investasi.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-semibold text-base text-[#0f172a]">Perubahan Konten</h2>
            <p>
              IDXDaily berhak mengubah, memperbarui, atau menghapus konten kapan saja tanpa
              pemberitahuan sebelumnya. Disclaimer ini dapat diperbarui sewaktu-waktu.
              Penggunaan situs ini setelah perubahan disclaimer berarti Anda menyetujui
              versi terbaru.
            </p>
          </section>

          <p className="text-xs text-stone-500 border-t border-stone-100 pt-4">
            Pertanyaan? Hubungi kami di{' '}
            <a href="mailto:vrbarlian@gmail.com" className="underline">vrbarlian@gmail.com</a>.
          </p>

        </div>
      </main>
    </div>
  );
}
