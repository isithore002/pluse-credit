// frontend/app/layout.tsx

import type { Metadata } from 'next';
import { Manrope, Space_Grotesk } from 'next/font/google';
import AppShell from '@/components/AppShell';
import './globals.css';

const manrope = Manrope({
  subsets: ['latin'],
  variable: '--font-manrope',
  display: 'swap',
});

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-space-grotesk',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'PulseCredit - Behavioral Credit Scoring',
  description:
    'Alternative credit scoring for India\'s 350M credit-invisible population',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${manrope.variable} ${spaceGrotesk.variable}`}>
        <div className="mesh-bg min-h-screen overflow-hidden">
          <div className="pointer-events-none absolute left-[-220px] top-[-220px] h-[460px] w-[460px] rounded-full bg-cyan-300/10 blur-3xl"></div>
          <div className="pointer-events-none absolute right-[-190px] top-[35%] h-[420px] w-[420px] rounded-full bg-sky-300/10 blur-3xl"></div>
          <AppShell>{children}</AppShell>
        </div>
      </body>
    </html>
  );
}
