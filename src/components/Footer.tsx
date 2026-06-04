import Link from 'next/link';

export default function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-[#e5e2db] bg-white mt-12">
      <div className="max-w-5xl mx-auto px-4 py-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-stone-500">
        <span>© {year} IHSGDaily. Bukan saran investasi.</span>
        <nav className="flex items-center gap-4 flex-wrap justify-center">
          <Link href="/tentang" className="hover:text-stone-800 transition-colors">
            Tentang
          </Link>
          <Link href="/disclaimer" className="hover:text-stone-800 transition-colors">
            Disclaimer
          </Link>
          <Link href="/kebijakan-privasi" className="hover:text-stone-800 transition-colors">
            Kebijakan Privasi
          </Link>
          <a href="mailto:vrbarlian@gmail.com" className="hover:text-stone-800 transition-colors">
            Kontak
          </a>
        </nav>
      </div>
    </footer>
  );
}
