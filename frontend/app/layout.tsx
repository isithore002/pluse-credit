// frontend/app/layout.tsx

import type { Metadata } from 'next';
import './globals.css';

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
      <body>
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
          <header className="border-b border-slate-700 bg-slate-800/50 backdrop-blur-sm">
            <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500"></div>
                  <h1 className="text-2xl font-bold text-white">PulseCredit</h1>
                </div>
                <p className="text-sm text-slate-400">
                  Behavioral credit scoring for the 350M invisible
                </p>
              </div>
            </div>
          </header>
          <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
