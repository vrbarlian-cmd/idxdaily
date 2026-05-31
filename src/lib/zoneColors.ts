/**
 * Zone color mapping for the Fear & Greed Index.
 * No Prisma dependency — safe to import in client components.
 */

export interface ZoneStyle {
  bg:    string;  // Tailwind bg class  (filled circle)
  text:  string;  // Tailwind text class (label)
  hex:   string;  // Raw CSS hex         (SVG fills)
  label: string;  // Display label
}

export function zoneColors(score: number | null): ZoneStyle {
  if (score == null)  return { bg: 'bg-stone-300',  text: 'text-stone-400',  hex: '#d6d3d1', label: 'No Data'      };
  if (score < 25)     return { bg: 'bg-red-500',    text: 'text-red-600',    hex: '#ef4444', label: 'Extreme Fear' };
  if (score < 45)     return { bg: 'bg-orange-500', text: 'text-orange-600', hex: '#f97316', label: 'Fear'         };
  if (score < 55)     return { bg: 'bg-yellow-500', text: 'text-yellow-600', hex: '#eab308', label: 'Neutral'      };
  if (score < 75)     return { bg: 'bg-lime-500',   text: 'text-lime-600',   hex: '#84cc16', label: 'Greed'        };
  return                     { bg: 'bg-green-600',  text: 'text-green-700',  hex: '#16a34a', label: 'Extreme Greed'};
}
