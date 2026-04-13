'use client';

// components/ScoreRing.tsx - Animated score ring display

import { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';

interface ScoreRingProps {
  score: number;
  band: string;
}

export default function ScoreRing({ score, band }: ScoreRingProps) {
  const canvasRef = useRef<SVGCircleElement>(null);

  // Color based on band
  const colorMap: Record<string, string> = {
    poor: '#E24B4A',
    fair: '#F59E0B',
    good: '#10B981',
    very_good: '#3B82F6',
    excellent: '#8B5CF6',
  };

  const color = colorMap[band] || '#10B981';

  // Calculate stroke-dasharray
  const circumference = 2 * Math.PI * 80;
  const offset = circumference * (1 - (score - 300) / 550);

  return (
    <div className="flex flex-col items-center justify-center">
      <svg width="280" height="280" className="drop-shadow-2xl">
        {/* Background circle */}
        <circle cx="140" cy="140" r="80" fill="none" stroke="#334155" strokeWidth="8" />

        {/* Animated progress circle */}
        <motion.circle
          ref={canvasRef}
          cx="140"
          cy="140"
          r="80"
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={circumference}
          strokeLinecap="round"
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.5, ease: 'easeOut' }}
        />
      </svg>

      {/* Score text */}
      <motion.div
        className="text-center"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8 }}
      >
        <motion.div
          className="text-6xl font-bold text-gradient"
          initial={{ scale: 0.5 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.5, type: 'spring' }}
        >
          {score}
        </motion.div>
        <div className="mt-2 text-lg text-slate-400">/850</div>
        <div className="mt-4 rounded-lg bg-slate-800 px-4 py-2 text-sm font-semibold uppercase tracking-wider text-slate-300 capitalize">
          {band.replace('_', ' ')}
        </div>
      </motion.div>

      {/* Score range indicator */}
      <div className="mt-8 w-full max-w-xs space-y-2">
        <div className="flex justify-between text-xs text-slate-400">
          <span>Poor</span>
          <span>Fair</span>
          <span>Good</span>
          <span>Great</span>
          <span>Excellent</span>
        </div>
        <div className="h-2 rounded-full bg-gradient-to-r from-red-500 via-yellow-500 via-green-500 to-purple-500"></div>
        <div className="flex justify-between text-xs text-slate-400">
          <span>300</span>
          <span>600</span>
          <span>700</span>
          <span>750</span>
          <span>850</span>
        </div>
      </div>
    </div>
  );
}
