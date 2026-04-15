'use client';

// components/SHAPWaterfall.tsx - Feature impact waterfall chart

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

interface ShapValue {
  feature: string;
  value: number;
  impact: number;
}

interface SHAPWaterfallProps {
  shap: ShapValue[];
}

export default function SHAPWaterfall({ shap }: SHAPWaterfallProps) {
  const data = shap.map((item) => ({
    name: item.feature,
    value: Math.abs(item.impact),
    impact: item.impact,
    positive: item.impact > 0,
    rawValue: item.value,
  }));

  // Sort by absolute impact descending
  data.sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact));

  const hasData = data.length > 0;
  const hasVisibleImpact = data.some((item) => Math.abs(item.impact) > 1e-6);

  if (!hasData) {
    return (
      <div className="rounded-lg border border-slate-700/70 bg-slate-900/30 p-5 text-slate-300">
        No SHAP feature data is available for this score yet.
      </div>
    );
  }

  if (!hasVisibleImpact) {
    return (
      <div className="space-y-4">
        <div className="rounded-lg border border-slate-700/70 bg-slate-900/30 p-5">
          <p className="text-sm font-semibold uppercase tracking-wide text-amber-300">Flat Attribution</p>
          <p className="mt-2 text-sm text-slate-300">
            Top SHAP impacts are near zero for this profile, so no dominant feature is driving the score alone.
          </p>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          {data.map((item) => (
            <div key={item.name} className="rounded-lg border border-slate-700/60 bg-slate-900/20 p-3">
              <p className="truncate text-sm font-semibold text-slate-200">{item.name}</p>
              <p className="mt-1 text-xs text-slate-400">Feature value: {Number(item.rawValue).toFixed(2)}</p>
              <p className="mt-1 text-xs text-slate-500">SHAP impact: 0.00</p>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 5, right: 30, left: 200, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
          <XAxis type="number" stroke="#94A3B8" />
          <YAxis dataKey="name" type="category" width={190} stroke="#94A3B8" tick={{ fill: '#CBD5E1', fontSize: 12 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1E293B',
              border: '1px solid #475569',
              borderRadius: '8px',
            }}
            formatter={(value, name) => {
              if (name === 'value') return Math.abs(Number(value)).toFixed(1);
              return value;
            }}
          />
          <Bar dataKey="value" radius={[0, 8, 8, 0]}>
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.impact > 0 ? '#10B981' : '#EF4444'}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="mt-4 flex gap-6">
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded bg-green-500"></div>
          <span className="text-sm text-slate-300">Positive Impact</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded bg-red-500"></div>
          <span className="text-sm text-slate-300">Negative Impact</span>
        </div>
      </div>
    </div>
  );
}
