import type { Metadata } from 'next';

// Internal pages: never indexed (also disallowed in robots.ts, not in sitemap).
export const metadata: Metadata = {
  title: 'Admin | DailyIHSG',
  robots: { index: false, follow: false },
};

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return children;
}
