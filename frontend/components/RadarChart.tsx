'use client';

// components/RadarChart.tsx - 6-axis behavioral dimensions radar

import { PureComponent } from 'react';
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { DimensionScores } from '@/lib/store';

interface RadarChartProps {
  dimensions: DimensionScores;
}

export default function BehavioralRadar({ dimensions }: RadarChartProps) {
  const data = [
    { name: 'Rhythm', value: dimensions.rhythm },
    { name: 'Merchant Consistency', value: dimensions.merchant },
    { name: 'Social Trust', value: dimensions.social },
    { name: 'Calendar Alignment', value: dimensions.calendar },
    { name: 'Velocity Stability', value: dimensions.velocity },
    { name: 'NLP Intent', value: dimensions.nlp },
  ];

  return (
    <div className="h-96 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data}>
          <PolarGrid stroke="#475569" />
          <PolarAngleAxis dataKey="name" stroke="#94A3B8" tick={{ fill: '#CBD5E1' }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} stroke="#64748B" />
          <Radar
            name="Your Score"
            dataKey="value"
            stroke="#A78BFA"
            fill="#8B5CF6"
            fillOpacity={0.3}
          />
          <Legend />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
