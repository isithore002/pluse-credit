'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiService } from '@/lib/api';
import { DimensionScores, usePulseCreditStore } from '@/lib/store';

const DIMENSIONS: Array<{ key: keyof DimensionScores; label: string }> = [
  { key: 'rhythm', label: 'Payment Rhythm' },
  { key: 'merchant', label: 'Merchant Consistency' },
  { key: 'social', label: 'Social Trust' },
  { key: 'calendar', label: 'Calendar Alignment' },
  { key: 'velocity', label: 'Velocity Stability' },
  { key: 'nlp', label: 'NLP Intent' },
];

export default function SimulatePage() {
  const router = useRouter();
  const store = usePulseCreditStore();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const baseScore = store.score;

  if (!baseScore) {
    return (
      <div className="card">
        <h2 className="text-2xl font-bold text-white">What-If Simulator</h2>
        <p className="mt-3 text-slate-300">Load a profile first from upload or demo personas.</p>
        <button className="btn-secondary mt-6" onClick={() => router.push('/')}>
          Go To Home
        </button>
      </div>
    );
  }

  const effectiveDimensions: DimensionScores = {
    ...baseScore.dimensions,
    ...store.simulatorOverrides,
  };

  const handleSlider = (key: keyof DimensionScores, value: number) => {
    store.setSimulatorOverride(key, value);
  };

  const runSimulation = async () => {
    if (!store.profileId && !baseScore.profile_id) return;

    setIsSubmitting(true);
    store.setError(null);

    try {
      const result = await apiService.simulateScore(
        store.profileId || baseScore.profile_id,
        store.simulatorOverrides as Record<string, number>
      );
      store.setSimulatedScore(result);
    } catch (error) {
      store.setError(`Simulation failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-8 py-8">
      <section>
        <h2 className="text-3xl font-bold text-white">What-If Simulator</h2>
        <p className="mt-2 text-slate-400">Adjust behavioral dimensions and re-score instantly.</p>
      </section>

      <section className="card">
        <div className="grid gap-6">
          {DIMENSIONS.map((dim) => (
            <div key={dim.key}>
              <div className="mb-2 flex items-center justify-between">
                <label className="text-sm font-semibold text-slate-200">{dim.label}</label>
                <span className="text-sm text-slate-300">{effectiveDimensions[dim.key]}</span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={effectiveDimensions[dim.key]}
                onChange={(e) => handleSlider(dim.key, Number(e.target.value))}
                className="w-full"
              />
            </div>
          ))}
        </div>

        <div className="mt-6 flex gap-3">
          <button className="btn-primary" onClick={runSimulation} disabled={isSubmitting}>
            {isSubmitting ? 'Running...' : 'Run Simulation'}
          </button>
          <button className="btn-secondary" onClick={() => store.resetSimulator()}>
            Reset
          </button>
          <button className="btn-secondary" onClick={() => router.push('/dashboard')}>
            Back To Dashboard
          </button>
        </div>
      </section>

      {store.simulatedScore && (
        <section className="card border border-emerald-700/60 bg-emerald-900/10">
          <h3 className="text-xl font-bold text-white">Simulation Result</h3>
          <p className="mt-2 text-slate-300">
            Base score: {baseScore.pulse_score} | Simulated score: {store.simulatedScore.pulse_score}
          </p>
          <p className="mt-1 text-emerald-300">Delta: {store.simulatedScore.pulse_score - baseScore.pulse_score}</p>
        </section>
      )}

      {store.error && <div className="rounded border border-red-700 bg-red-900/20 p-3 text-red-200">{store.error}</div>}
    </div>
  );
}
