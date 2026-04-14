'use client';

// frontend/app/dashboard/page.tsx - Main dashboard displaying score and results

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { usePulseCreditStore } from '@/lib/store';
import ScoreRing from '@/components/ScoreRing';
import RadarChart from '@/components/RadarChart';
import SHAPWaterfall from '@/components/SHAPWaterfall';
import ActionRoadmap from '@/components/ActionRoadmap';

export default function Dashboard() {
  const router = useRouter();
  const store = usePulseCreditStore();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted || !store.score) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="h-12 w-12 animate-spin rounded-full border-4 border-slate-600 border-t-purple-500 mx-auto"></div>
          <p className="mt-4 text-slate-300">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  const { score } = store;

  return (
    <div className="space-y-8 py-8">
      {/* Header */}
      <section>
        <h2 className="text-3xl font-bold text-white">Your PulseCredit Score</h2>
        <p className="mt-2 text-slate-400">
          Based on {store.transactions.length} transactions • {score.archetype}
        </p>
      </section>

      {/* Main score display */}
      <section className="card grid gap-8 lg:grid-cols-2">
        <div>
          <ScoreRing score={score.pulse_score} band={score.band} />
        </div>

        <div className="flex flex-col justify-center space-y-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wider text-slate-400">Confidence Range</p>
            <p className="mt-2 text-2xl font-bold text-slate-200">
              {score.confidence_interval[0]} – {score.confidence_interval[1]}
            </p>
          </div>

          <div>
            <p className="text-sm font-semibold uppercase tracking-wider text-slate-400">Category</p>
            <p className="mt-2 text-2xl font-bold text-gradient capitalize">
              {score.band.replace('_', ' ')}
            </p>
          </div>

          <div>
            <p className="text-sm font-semibold uppercase tracking-wider text-slate-400">Archetype</p>
            <p className="mt-2 text-2xl font-bold text-slate-200 capitalize">
              {score.archetype}
            </p>
          </div>

          <div className="border-t border-slate-700 pt-4">
            <p className="text-sm text-slate-400">{score.explanation}</p>
          </div>
        </div>
      </section>

      {/* Behavioral dimensions */}
      <section className="card">
        <h3 className="mb-6 text-2xl font-bold text-white">Behavioral Dimensions</h3>
        <RadarChart dimensions={score.dimensions} />
      </section>

      {/* SHAP top features */}
      <section className="card">
        <h3 className="mb-6 text-2xl font-bold text-white">What's Driving Your Score</h3>
        <SHAPWaterfall shap={score.shap_top3} />
      </section>

      {/* Action roadmap */}
      <section className="card">
        <h3 className="mb-6 text-2xl font-bold text-white">3-Month Roadmap to Improve</h3>
        <ActionRoadmap actions={score.actions} />
      </section>

      {/* Lender memo */}
      <section className="card border-l-4 border-l-purple-500 bg-purple-900/10">
        <h3 className="mb-4 text-lg font-bold text-white">Lender Credit Memo</h3>
        <p className="whitespace-pre-wrap text-sm text-slate-300">{score.lender_memo}</p>
      </section>

      {/* Navigation buttons */}
      <section className="flex gap-4">
        <button
          className="btn-primary"
          onClick={() => router.push(`/report?profile_id=${score.profile_id}`)}
        >
          Download PDF Report
        </button>
        <button
          className="btn-secondary"
          onClick={() => router.push('/simulate')}
        >
          What-If Simulator
        </button>
        <button
          className="btn-secondary"
          onClick={() => {
            store.reset();
            router.push('/');
          }}
        >
          New Upload
        </button>
      </section>
    </div>
  );
}
