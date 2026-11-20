import Link from 'next/link';
import HeaderSearchConditional from '@/components/HeaderSearchConditional';
import Logo from '@/components/Logo';
import type { MarketSnapshot } from '@/lib/marketData';

interface HeaderProps {
  market?: MarketSnapshot | null;
}

function MarketPill({
  label,
  value,
  change,
}: {
  label: string;
  value: string;
  change?: number | null;
}) {
  const changeClass =
    change == null ? '' : change >= 0 ? 'text-emerald-600' : 'text-red-600';
  const changeStr =
    change == null ? '' : (change >= 0 ? '+' : '') + change.toFixed(2) + '%';

  return (
    <div className="flex items-center gap-1.5 px-2">
      <span className="text-xs text-[#9ca3af] font-medium">{label}</span>
      <span className="text-sm font-mono font-bold text-[#0f172a]">{value}</span>
      {changeStr && (
        <span className={`text-xs font-mono font-semibold ${changeClass}`}>{changeStr}</span>
      )}
    </div>
  );
}

export default function Header({ market }: HeaderProps) {
  const fmt = (n: number | null, dec = 0) =>
    n == null
      ? '—'
      : n.toLocaleString('id-ID', { minimumFractionDigits: dec, maximumFractionDigits: dec });

  return (
    <header className="bg-white border-b border-[#e5e2db] sticky top-0 z-50">
      <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between gap-4">
        {/* Brand */}
        <Link
          href="/"
          className="flex items-center hover:opacity-75 transition-opacity flex-shrink-0"
        >
          <Logo height={48} />
        </Link>

        {/* Centre: search — hidden on homepage (hero search handles it there) */}
        <div className="flex-1 flex justify-center px-2">
          <HeaderSearchConditional />
        </div>

        {/* Main nav (desktop) */}
        <nav className="hidden md:block flex-shrink-0">
          <Link href="/fear-greed" className="text-sm font-semibold text-[#374151] hover:text-[#1a56db] transition-colors">
            Fear &amp; Greed
          </Link>
        </nav>

        {/* Market pills */}
        {market && (
          <div className="hidden md:flex items-center divide-x divide-[#e5e2db] flex-shrink-0">
            <MarketPill
              label="IHSG"
              value={fmt(market.ihsgValue)}
              change={market.ihsgChangePercent}
            />
            <MarketPill label="USD/IDR" value={fmt(market.usdIdr)} />
          </div>
        )}
      </div>

      {/* Phones: nav link + compact market strip under the logo row */}
      <div className="md:hidden border-t border-[#f0ede8] bg-[#fbfaf8]">
        <div className="px-4 h-8 flex items-center justify-center divide-x divide-[#e5e2db]">
          <Link href="/fear-greed" className="px-2 text-xs font-semibold text-[#1a56db] whitespace-nowrap">
            Fear &amp; Greed
          </Link>
          {market && (
            <>
              <MarketPill
                label="IHSG"
                value={fmt(market.ihsgValue)}
                change={market.ihsgChangePercent}
              />
              <MarketPill label="USD/IDR" value={fmt(market.usdIdr)} />
            </>
          )}
        </div>
      </div>
    </header>
  );
}
