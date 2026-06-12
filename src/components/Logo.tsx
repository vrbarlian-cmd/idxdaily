interface LogoProps {
  /** Overall height in px. Width scales proportionally. Default: 36 */
  height?: number;
  /** Render only the candlestick icon (no wordmark). Default: false */
  iconOnly?: boolean;
}

// Brand palette
const GREEN = '#1D9E75';
const RED   = '#E24B4A';
const DARK  = '#1A2332';

/**
 * DailyIHSG brand logo.
 *
 * iconOnly=false → candlestick icon + "DailyIHSG" wordmark (Daily bold dark,
 *                  IHSG light green) — font inherits site Inter.
 * iconOnly=true  → three-candle icon only (compact contexts / favicon).
 */
export default function Logo({ height = 36, iconOnly = false }: LogoProps) {
  // Candlestick mark — green / red / green. viewBox 28×36 (from brand spec).
  const markWidth = Math.round(height * (28 / 36));
  const Candles = (
    <svg
      viewBox="0 0 28 36"
      height={height}
      width={markWidth}
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden={iconOnly ? undefined : true}
      aria-label={iconOnly ? 'DailyIHSG' : undefined}
      role={iconOnly ? 'img' : undefined}
    >
      {/* Green candle (left) */}
      <rect x="1" y="10" width="6" height="16" rx="1.5" fill={GREEN} />
      <line x1="4" y1="4"  x2="4" y2="10" stroke={GREEN} strokeWidth="2" />
      <line x1="4" y1="26" x2="4" y2="32" stroke={GREEN} strokeWidth="2" />
      {/* Red candle (centre) */}
      <rect x="11" y="4" width="6" height="22" rx="1.5" fill={RED} />
      <line x1="14" y1="0"  x2="14" y2="4"  stroke={RED} strokeWidth="2" />
      <line x1="14" y1="26" x2="14" y2="32" stroke={RED} strokeWidth="2" />
      {/* Green candle (right) */}
      <rect x="21" y="8" width="6" height="16" rx="1.5" fill={GREEN} />
      <line x1="24" y1="2"  x2="24" y2="8"  stroke={GREEN} strokeWidth="2" />
      <line x1="24" y1="24" x2="24" y2="30" stroke={GREEN} strokeWidth="2" />
    </svg>
  );

  if (iconOnly) return Candles;

  const fontSize = Math.round(height * 0.62);

  return (
    <span className="inline-flex items-center gap-2.5 select-none">
      {Candles}
      {/* Wordmark + tagline, stacked */}
      <span className="flex flex-col">
        {/* Wordmark — HTML so it inherits site Inter font */}
        <span className="tracking-tight leading-none" style={{ fontSize, letterSpacing: '-0.5px' }}>
          <span style={{ color: DARK,  fontWeight: 700 }}>Daily</span>
          <span style={{ color: GREEN, fontWeight: 300 }}>IHSG</span>
        </span>
        {/* Tagline — always visible; smaller on very small screens */}
        <span
          className="block uppercase text-[8px] sm:text-[10px] tracking-widest sm:tracking-[1.5px]"
          style={{
            color: '#6B7280',
            lineHeight: 1,
            marginTop: '2px',
            whiteSpace: 'nowrap',
          }}
        >
          Berita &amp; Sentimen Pasar Indonesia
        </span>
      </span>
    </span>
  );
}
