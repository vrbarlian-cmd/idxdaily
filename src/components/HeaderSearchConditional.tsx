'use client';

import { usePathname } from 'next/navigation';
import HeaderSearch from '@/components/HeaderSearch';

/**
 * Renders the header search bar on every route EXCEPT the homepage (/).
 * On the homepage the hero search is the primary search — no duplication needed.
 */
export default function HeaderSearchConditional() {
  const pathname = usePathname();
  if (pathname === '/') return null;
  return <HeaderSearch />;
}
