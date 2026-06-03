import './globals.css';
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import Header from '@/components/Header';
import Footer from '@/components/Footer';
import { fetchMarketSnapshot } from '@/lib/marketData';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap' });

export const metadata: Metadata = {
  title: 'IDXDaily — Berita & sentimen pasar saham Indonesia, dirangkum AI',
  description: 'Agregator berita saham IDX dengan analisis sentimen AI real-time. Fear & Greed index, berita makro, dan sinyal pasar terkini.',
  keywords: 'saham IDX, berita saham, sentimen, AI, Indonesia, IHSG, IDXDaily',
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const market = await fetchMarketSnapshot().catch(() => null);

  return (
    <html lang="id" className={inter.variable}>
      <body className="font-sans antialiased">
        <Header market={market} />
        {children}
        <Footer />
      </body>
    </html>
  );
}
