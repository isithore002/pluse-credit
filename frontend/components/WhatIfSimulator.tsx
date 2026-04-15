'use client';

import { DimensionScores } from '@/lib/store';

interface WhatIfSimulatorProps {
  dimensions: DimensionScores;
  overrides: Partial<DimensionScores>;
  onChange: (key: keyof DimensionScores, value: number) => void;
  onRun: () => void;
  onReset: () => void;
  onBack: () => void;
  isSubmitting?: boolean;
}

const DIMENSIONS: Array<{ key: keyof DimensionScores; label: string }> = [
  { key: 'rhythm', label: 'Payment Rhythm' },
  { key: 'merchant', label: 'Merchant Consistency' },
  { key: 'social', label: 'Social Trust' },
  { key: 'calendar', label: 'Calendar Alignment' },
  { key: 'velocity', label: 'Velocity Stability' },
  { key: 'nlp', label: 'NLP Intent' },
];

export default function WhatIfSimulator({
  dimensions,
  overrides,
  onChange,
  onRun,
  onReset,
  onBack,
  isSubmitting,
}: WhatIfSimulatorProps) {
  const effective: DimensionScores = {
    ...dimensions,
    ...overrides,
  };

  return (
    <section className="card">
      <div className="grid gap-6">
        {DIMENSIONS.map((dim) => (
          <div key={dim.key}>
            <div className="mb-2 flex items-center justify-between">
              <label className="text-sm font-semibold text-slate-200">{dim.label}</label>
              <span className="text-sm text-slate-300">{effective[dim.key]}</span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              value={effective[dim.key]}
              onChange={(e) => onChange(dim.key, Number(e.target.value))}
              className="w-full"
            />
          </div>
        ))}
      </div>

      <div className="mt-6 flex gap-3">
        <button className="btn-primary" onClick={onRun} disabled={isSubmitting}>
          {isSubmitting ? 'Running...' : 'Run Simulation'}
        </button>
        <button className="btn-secondary" onClick={onReset}>
          Reset
        </button>
        <button className="btn-secondary" onClick={onBack}>
          Back To Dashboard
        </button>
      </div>
    </section>
  );
}
