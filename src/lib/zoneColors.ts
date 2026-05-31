/**
 * Zone color mapping for the Fear & Greed Index.
 * No Prisma dependency — safe to import in client components.
 *
 * Palette: muted, editorial fintech tones (not loud dashboard colors).
 */

export interface ZoneStyle {
  bg:    string;  // Tailwind bg class  (filled circle / badge)
  text:  string;  // Tailwind text class (label / score)
  hex:   string;  // Raw CSS hex         (SVG fills)
  label: string;  // Display label
}

export function zoneColors(score: number | null): ZoneStyle {
  if (score == null)  return { bg: 'bg-stone-300',    text: 'text-[#9ca3af]',  hex: '#d1cdc7', label: 'No Data'       };
  if (score < 25)     return { bg: 'bg-red-700',      text: 'text-[#b91c1c]',  hex: '#b91c1c', label: 'Extreme Fear'  };
  if (score < 45)     return { bg: 'bg-amber-600',    text: 'text-[#d97706]',  hex: '#d97706', label: 'Fear'          };
  if (score < 55)     return { bg: 'bg-stone-500',    text: 'text-[#6b7280]',  hex: '#6b7280', label: 'Neutral'       };
  if (score < 75)     return { bg: 'bg-emerald-600',  text: 'text-[#059669]',  hex: '#059669', label: 'Greed'         };
  return                     { bg: 'bg-emerald-800',  text: 'text-[#047857]',  hex: '#047857', label: 'Extreme Greed' };
}
