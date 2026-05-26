import Link from 'next/link';
import HeaderSearch from '@/components/HeaderSearch';
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
    change == null ? '' : change >= 0 ? 'text-bull-600' : 'text-bear-600';
  const changeStr =
    change == null ? '' : (change >= 0 ? '+' : '') + change.toFixed(2) + '%';

  return (
    <div className="flex items-center gap-1.5 bg-stone-50 border border-stone-200 rounded-full px-3 py-1">
      <span className="text-xs text-stone-500 font-medium">{label}</span>
      <span className="text-xs font-mono font-semibold text-stone-800">{value}</span>
      {changeStr && (
        <span className={`text-xs font-mono font-medium ${changeClass}`}>{changeStr}</span>
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
    <header className="bg-white border-b border-stone-200 sticky top-0 z-50">
      <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between gap-4">
        {/* Brand — slightly smaller on mobile so search bar has room */}
        <Link
          href="/"
          className="flex items-center hover:opacity-80 transition-opacity flex-shrink-0"
        >
          <span className="sm:hidden"><Logo height={36} /></span>
          <span className="hidden sm:inline-flex"><Logo height={44} /></span>
        </Link>

        {/* Centre: search */}
        <div className="flex-1 flex justify-center px-2">
          <HeaderSearch />
        </div>

        {/* Market pills */}
        {market && (
          <div className="hidden md:flex items-center gap-2 flex-shrink-0">
            <MarketPill
              label="IHSG"
              value={fmt(market.ihsgValue)}
              change={market.ihsgChangePercent}
            />
            <MarketPill label="USD/IDR" value={fmt(market.usdIdr)} />
          </div>
        )}
      </div>
    </header>
  );
}
