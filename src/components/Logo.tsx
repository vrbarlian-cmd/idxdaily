interface LogoProps {
  /** Overall height in px. Width scales proportionally. Default: 36 */
  height?: number;
  /** Render only the candlestick icon (dark rounded square). Default: false */
  iconOnly?: boolean;
}

/**
 * SahamDaily brand logo.
 *
 * iconOnly=false → candlestick icon + "SahamDaily" wordmark (font inherits site Inter)
 * iconOnly=true  → dark rounded-square icon only (used for favicon / compact contexts)
 */
export default function Logo({ height = 36, iconOnly = false }: LogoProps) {
  if (iconOnly) {
    return (
      <svg
        viewBox="0 0 96 96"
        height={height}
        width={height}
        xmlns="http://www.w3.org/2000/svg"
        aria-label="SahamDaily"
        role="img"
      >
        {/* Dark rounded background */}
        <rect width="96" height="96" rx="20" fill="#0f172a" />

        {/* Candle 1 — bullish teal (left) */}
        <line x1="32" y1="12" x2="32" y2="80" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
        <rect x="26" y="28" width="12" height="36" rx="2" fill="#0d9488" />

        {/* Candle 2 — bearish red (centre) */}
        <line x1="50" y1="18" x2="50" y2="84" stroke="#f43f5e" strokeWidth="2.5" strokeLinecap="round" />
        <rect x="44" y="36" width="12" height="34" rx="2" fill="#f43f5e" />

        {/* Candle 3 — bullish teal (right) */}
        <line x1="68" y1="16" x2="68" y2="76" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
        <rect x="62" y="24" width="12" height="30" rx="2" fill="#0d9488" />
      </svg>
    );
  }

  // Full logo: inline icon (no background) + HTML wordmark so font matches site Inter
  const iconWidth = Math.round(height * 0.75);
  const fontSize  = Math.round(height * 0.62);

  return (
    <span className="inline-flex items-center gap-2 select-none">
      {/* Candlestick marks — no background for header use */}
      <svg
        viewBox="0 0 60 80"
        height={height}
        width={iconWidth}
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        {/* Candle 1 — bullish teal */}
        <line x1="10" y1="6" x2="10" y2="66" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
        <rect x="4" y="20" width="12" height="30" rx="2" fill="#0d9488" />

        {/* Candle 2 — bearish red */}
        <line x1="30" y1="12" x2="30" y2="72" stroke="#f43f5e" strokeWidth="2.5" strokeLinecap="round" />
        <rect x="24" y="28" width="12" height="28" rx="2" fill="#f43f5e" />

        {/* Candle 3 — bullish teal */}
        <line x1="50" y1="4" x2="50" y2="62" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
        <rect x="44" y="16" width="12" height="26" rx="2" fill="#0d9488" />
      </svg>

      {/* Wordmark — rendered as HTML so it inherits site Inter font */}
      <span className="font-bold tracking-tight leading-none" style={{ fontSize }}>
        <span className="text-stone-900">Saham</span>
        <span style={{ color: '#0d9488' }}>Daily</span>
      </span>
    </span>
  );
}
