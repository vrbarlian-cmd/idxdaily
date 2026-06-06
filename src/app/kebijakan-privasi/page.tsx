import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Kebijakan Privasi - SahamDaily',
  description: 'Kebijakan privasi SahamDaily: data apa yang dikumpulkan dan bagaimana penggunaannya.',
};

export default function KebijakanPrivasiPage() {
  return (
    <div className="min-h-screen bg-stone-50">
      <main className="max-w-3xl mx-auto px-4 py-10 space-y-6">
        <h1 className="text-2xl font-bold text-[#0f172a]">Kebijakan Privasi</h1>
        <p className="text-xs text-stone-500">Terakhir diperbarui: Juni 2026</p>

        <div className="bg-white rounded-xl border border-stone-200 p-6 space-y-5 text-sm text-stone-700 leading-relaxed">

          <section className="space-y-2">
            <h2 className="font-semibold text-base text-[#0f172a]">Data yang Kami Kumpulkan</h2>
            <p>
              SahamDaily mengumpulkan data yang sangat minimal dan tidak bersifat pribadi:
            </p>
            <ul className="list-disc list-inside space-y-1 pl-2">
              <li>
                <span className="font-medium">Log pencarian ticker</span> - ketika Anda mencari
                kode saham (misalnya &ldquo;BBCA&rdquo;), kami menyimpan kode saham tersebut dan
                waktu pencarian. Tidak ada nama, email, atau identitas yang disimpan.
              </li>
              <li>
                <span className="font-medium">Statistik kunjungan halaman</span> - data agregat
                seperti halaman yang paling banyak dikunjungi, digunakan untuk memahami konten
                mana yang paling berguna.
              </li>
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="font-semibold text-base text-[#0f172a]">Data yang Tidak Kami Kumpulkan</h2>
            <p>
              SahamDaily tidak memiliki sistem akun pengguna. Kami tidak mengumpulkan nama, alamat
              email, nomor telepon, atau informasi pribadi lainnya. Tidak ada cookie pelacak pihak
              ketiga yang digunakan saat ini.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-semibold text-base text-[#0f172a]">Google Analytics</h2>
            <p>
              Kami berencana mengintegrasikan Google Analytics untuk statistik kunjungan agregat.
              Jika diaktifkan, Google Analytics dapat menggunakan cookie untuk mengukur penggunaan
              situs secara anonim. Anda dapat menonaktifkannya melalui ekstensi browser Google
              Analytics Opt-out.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-semibold text-base text-[#0f172a]">Iklan (Google AdSense)</h2>
            <p>
              SahamDaily menggunakan Google AdSense untuk menampilkan iklan. Google AdSense dapat
              menggunakan cookie untuk menampilkan iklan yang relevan berdasarkan kunjungan Anda
              sebelumnya ke situs ini atau situs lain. Anda dapat menonaktifkan penggunaan cookie
              iklan berbasis minat di{' '}
              <a href="https://www.google.com/settings/ads" className="underline text-stone-500"
                target="_blank" rel="noopener noreferrer">
                Pengaturan Iklan Google
              </a>.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-semibold text-base text-[#0f172a]">Keamanan Data</h2>
            <p>
              Log pencarian disimpan di database terenkripsi dan hanya digunakan untuk fitur
              &ldquo;Populer&rdquo; (ticker yang paling banyak dicari). Data tidak dijual atau
              dibagikan kepada pihak ketiga.
            </p>
          </section>

          <section className="space-y-2">
            <h2 className="font-semibold text-base text-[#0f172a]">Hak Anda</h2>
            <p>
              Karena kami tidak menyimpan data pribadi yang dapat mengidentifikasi Anda, tidak ada
              data yang perlu dihapus. Untuk pertanyaan terkait privasi, hubungi kami di{' '}
              <a href="mailto:vrbarlian@gmail.com" className="underline text-stone-500">
                vrbarlian@gmail.com
              </a>.
            </p>
          </section>

        </div>
      </main>
    </div>
  );
}
