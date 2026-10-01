import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'MetricPilot — Product Analytics Investigation',
  description: 'Investigate synthetic product metrics with validated SQL, statistical tools, and inspectable evidence.',
};
export default function RootLayout({ children }: Readonly<{children: React.ReactNode}>) {
  return <html lang="en"><body>{children}</body></html>;
}
