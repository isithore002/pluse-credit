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
  const aiMode = score.ai_insights_mode === 'live' ? 'live' : 'fallback';

  const memoSections = (() => {
    const raw = score.lender_memo || '';
    const parsed = {
      profile: '',
      positive: '',
      risk: '',
      recommendation: '',
    };

    const markdownParts = raw.split(/\*\*Profile Summary\*\*|\*\*Positive Signals\*\*|\*\*Risk Indicators\*\*|\*\*Recommendation\*\*/g).map((s) => s.trim()).filter(Boolean);
    if (markdownParts.length >= 4) {
      parsed.profile = markdownParts[0];
      parsed.positive = markdownParts[1];
      parsed.risk = markdownParts[2];
      parsed.recommendation = markdownParts[3];
      return parsed;
    }

    const normalized = raw
      .replace(/\*\*/g, '')
      .replace(/\|/g, '\n')
      .replace(/Profile Summary:/i, 'Profile Summary\n')
      .replace(/Positive Signals:/i, '\nPositive Signals\n')
      .replace(/Risk Indicators:/i, '\nRisk Indicators\n')
      .replace(/Recommendation:/i, '\nRecommendation\n');

    const lines = normalized.split('\n').map((l) => l.trim()).filter(Boolean);
    let current: keyof typeof parsed | null = null;
    for (const line of lines) {
      const key = line.toLowerCase();
      if (key === 'profile summary') {
        current = 'profile';
        continue;
      }
      if (key === 'positive signals') {
        current = 'positive';
        continue;
      }
      if (key === 'risk indicators') {
        current = 'risk';
        continue;
      }
      if (key === 'recommendation') {
        current = 'recommendation';
        continue;
      }
      if (current) {
        parsed[current] = parsed[current] ? `${parsed[current]} ${line}` : line;
      }
    }
    return parsed;
  })();

  return (
    <div className="space-y-8 py-8">
      {/* Header */}
      <section className="surface">
        <h2 className="text-3xl font-bold text-white">Your PulseCredit Score</h2>
        <p className="mt-2 text-slate-400">
          Based on {store.transactions.length} transactions • {score.archetype}
        </p>
        <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-slate-300/20 bg-slate-900/45 px-3 py-1 text-xs font-semibold uppercase tracking-wide">
          <span
            className={`h-2 w-2 rounded-full ${
              aiMode === 'live' ? 'bg-emerald-400' : 'bg-amber-400'
            }`}
          ></span>
          <span className={aiMode === 'live' ? 'text-emerald-300' : 'text-amber-300'}>
            AI insights: {aiMode === 'live' ? 'Live' : 'Fallback mode'}
          </span>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="surface p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Pulse Score</p>
          <p className="mt-2 text-3xl font-bold text-white">{score.pulse_score}</p>
        </div>
        <div className="surface p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Confidence Span</p>
          <p className="mt-2 text-3xl font-bold text-white">
            {score.confidence_interval[1] - score.confidence_interval[0]}
          </p>
        </div>
        <div className="surface p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Top Positive Lift</p>
          <p className="mt-2 text-3xl font-bold text-emerald-300">
            +{Math.max(...score.shap_top3.map((s) => s.impact))}
          </p>
        </div>
        <div className="surface p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Action Plan Gain</p>
          <p className="mt-2 text-3xl font-bold text-cyan-200">
            +{score.actions.reduce((sum, action) => sum + action.delta, 0)}
          </p>
        </div>
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
        <h3 className="section-title mb-6">Behavioral Dimensions</h3>
        <RadarChart dimensions={score.dimensions} />
      </section>

      {/* SHAP top features */}
      <section className="card">
        <h3 className="section-title mb-6">What's Driving Your Score</h3>
        <SHAPWaterfall shap={score.shap_top3} />
      </section>

      {/* Action roadmap */}
      <section className="card">
        <h3 className="section-title mb-6">3-Month Roadmap to Improve</h3>
        <ActionRoadmap actions={score.actions} />
      </section>

      {/* Lender memo */}
      <section className="card border-l-4 border-l-cyan-300 bg-cyan-900/10">
        <h3 className="mb-4 text-lg font-bold text-white">Lender Credit Memo</h3>
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-lg border border-slate-700/70 bg-slate-900/25 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-cyan-200">Profile Summary</p>
            <p className="mt-2 text-sm text-slate-300">{memoSections.profile || 'Not available'}</p>
          </div>
          <div className="rounded-lg border border-slate-700/70 bg-slate-900/25 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-emerald-200">Positive Signals</p>
            <p className="mt-2 text-sm text-slate-300">{memoSections.positive || 'Not available'}</p>
          </div>
          <div className="rounded-lg border border-slate-700/70 bg-slate-900/25 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-200">Risk Indicators</p>
            <p className="mt-2 text-sm text-slate-300">{memoSections.risk || 'Not available'}</p>
          </div>
          <div className="rounded-lg border border-slate-700/70 bg-slate-900/25 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-fuchsia-200">Recommendation</p>
            <p className="mt-2 text-sm font-medium text-slate-100">{memoSections.recommendation || 'Not available'}</p>
          </div>
        </div>
      </section>

      {/* Navigation buttons */}
      <section className="flex flex-wrap gap-4">
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
          onClick={() => router.push('/graph')}
        >
          Social Graph
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
