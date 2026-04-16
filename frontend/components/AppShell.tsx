'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { usePathname } from 'next/navigation';
import { usePulseCreditStore } from '@/lib/store';

const navItems = [
  { href: '/', label: 'Home', hint: 'Upload and personas' },
  { href: '/dashboard', label: 'Dashboard', hint: 'Score and insights' },
  { href: '/simulate', label: 'Simulator', hint: 'What-if analysis' },
  { href: '/graph', label: 'Social Graph', hint: 'Trust network view' },
  { href: '/report', label: 'Lender Report', hint: 'PDF export' },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const score = usePulseCreditStore((state) => state.score);
  const transactions = usePulseCreditStore((state) => state.transactions);

  const scoreBand = useMemo(() => {
    if (!score) return 'No score yet';
    return score.band.replace('_', ' ');
  }, [score]);

  return (
    <div className="relative z-10 mx-auto flex min-h-screen max-w-[1400px] gap-6 px-3 py-4 sm:px-6 lg:px-8">
      <button
        type="button"
        className="btn-secondary fixed left-3 top-3 z-40 px-4 py-2 lg:hidden"
        onClick={() => setIsOpen((v) => !v)}
      >
        {isOpen ? 'Close' : 'Menu'}
      </button>

      <aside
        className={`fixed inset-y-0 left-0 z-30 w-72 border-r border-slate-200/15 bg-slate-950/80 p-5 backdrop-blur-2xl transition-transform duration-300 lg:static lg:translate-x-0 lg:rounded-2xl lg:border lg:bg-slate-950/45 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="mt-12 lg:mt-0">
          <div className="mb-6 rounded-2xl border border-cyan-200/20 bg-cyan-300/10 p-4">
            <p className="text-xs uppercase tracking-[0.15em] text-cyan-200">Workspace</p>
            <p className="mt-2 text-xl font-bold text-white">PulseCredit Console</p>
            <p className="mt-1 text-sm text-slate-200/80">Behavior-first credit intelligence</p>
          </div>

          <nav className="space-y-2">
            {navItems.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setIsOpen(false)}
                  className={`block rounded-xl border px-4 py-3 transition-all duration-200 ${
                    isActive
                      ? 'border-cyan-300/60 bg-cyan-200/15 text-white shadow-lg shadow-cyan-500/10'
                      : 'border-slate-200/10 bg-slate-900/40 text-slate-200 hover:border-cyan-300/35 hover:bg-slate-900/70'
                  }`}
                >
                  <p className="font-semibold">{item.label}</p>
                  <p className="text-xs text-slate-300/80">{item.hint}</p>
                </Link>
              );
            })}
          </nav>

          <div className="mt-6 rounded-xl border border-slate-200/15 bg-slate-900/45 p-4">
            <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Current Snapshot</p>
            <div className="mt-3 space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-300">Pulse Score</span>
                <span className="font-bold text-white">{score?.pulse_score ?? '--'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-300">Band</span>
                <span className="capitalize text-cyan-200">{scoreBand}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-300">Transactions</span>
                <span className="text-white">{transactions.length}</span>
              </div>
            </div>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="surface mb-4 flex items-center justify-between px-5 py-4">
          <div>
            <p className="text-xs uppercase tracking-[0.15em] text-slate-400">Credit Intelligence Workspace</p>
            <h2 className="text-lg font-semibold text-white">Decision Dashboard</h2>
          </div>
          <div className="rounded-full border border-cyan-200/30 bg-cyan-300/10 px-4 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-cyan-200">
            Hackathon Build
          </div>
        </header>

        <main className="min-w-0">{children}</main>
      </div>
    </div>
  );
}
