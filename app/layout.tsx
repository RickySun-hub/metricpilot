import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {
  title: 'MetricPilot | Evidence-grounded analytics',
  description: 'Inspect a recorded analytical investigation from question to SQL, cited answer and measured evaluation. Synthetic SaaS and public retail data; no paid requests in the showcase.',
};
export default function RootLayout({ children }: Readonly<{children: React.ReactNode}>) {
  return <html lang="en"><body>{children}</body></html>;
}
