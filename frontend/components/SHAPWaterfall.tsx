'use client';

// components/SHAPWaterfall.tsx - Feature impact waterfall chart

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
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
  }));

  // Sort by absolute impact descending
  data.sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact));

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
