// lib/store.ts - Zustand global state management

import { create } from 'zustand';

export interface Transaction {
  txn_date: string;
  amount: number;
  direction: 'DR' | 'CR';
  vpa: string;
  merchant_name: string;
  category: string;
  remarks: string;
}

export interface DimensionScores {
  rhythm: number;
  merchant: number;
  social: number;
  calendar: number;
  velocity: number;
  nlp: number;
}

export interface ShapValue {
  feature: string;
  value: number;
  impact: number;
}

export interface ScoreResult {
  profile_id: string;
  pulse_score: number;
  confidence_interval: [number, number];
  band: 'poor' | 'fair' | 'good' | 'very_good' | 'excellent';
  archetype: string;
  dimensions: DimensionScores;
  shap_top3: ShapValue[];
  explanation: string;
  actions: Array<{
    action: string;
    delta: number;
    priority: number;
  }>;
  lender_memo: string;
}

interface Persona {
  id: string;
  name: string;
  archetype: string;
  pulse_score: number;
  band: string;
  dimensions: DimensionScores;
  confidence?: [number, number] | number[];
  shap_top3?: ShapValue[];
}

interface PulseCreditStore {
  // Current profile data
  profileId: string | null;
  archetype: string | null;
  transactions: Transaction[];
  dimensions: DimensionScores | null;
  score: ScoreResult | null;

  // UI state
  isLoading: boolean;
  isUploading: boolean;
  error: string | null;
  currentPage: 'upload' | 'dashboard' | 'simulate' | 'graph' | 'report';

  // Demo personas
  personas: Persona[];
  activePersona: 'ravi' | 'priya' | 'arjun' | null;

  // Simulator state
  simulatorOverrides: Partial<DimensionScores>;
  simulatedScore: ScoreResult | null;

  // Actions
  setProfileId: (id: string) => void;
  setArchetype: (archetype: string) => void;
  setTransactions: (transactions: Transaction[]) => void;
  setScore: (score: ScoreResult) => void;
  setLoading: (loading: boolean) => void;
  setUploading: (uploading: boolean) => void;
  setError: (error: string | null) => void;
  setCurrentPage: (page: 'upload' | 'dashboard' | 'simulate' | 'graph' | 'report') => void;
  setPersonas: (personas: Persona[]) => void;
  loadPersona: (persona: 'ravi' | 'priya' | 'arjun') => void;
  setSimulatorOverride: (dim: keyof DimensionScores, value: number) => void;
  setSimulatedScore: (score: ScoreResult | null) => void;
  resetSimulator: () => void;
  reset: () => void;
}

export const usePulseCreditStore = create<PulseCreditStore>((set) => ({
  // Initial state
  profileId: null,
  archetype: null,
  transactions: [],
  dimensions: null,
  score: null,
  isLoading: false,
  isUploading: false,
  error: null,
  currentPage: 'upload',
  personas: [],
  activePersona: null,
  simulatorOverrides: {},
  simulatedScore: null,

  // Actions
  setProfileId: (id: string) => set({ profileId: id }),
  setArchetype: (archetype: string) => set({ archetype }),
  setTransactions: (transactions: Transaction[]) => set({ transactions }),
  setScore: (score: ScoreResult) => set({ score, currentPage: 'dashboard' }),
  setLoading: (loading: boolean) => set({ isLoading: loading }),
  setUploading: (uploading: boolean) => set({ isUploading: uploading }),
  setError: (error: string | null) => set({ error }),
  setCurrentPage: (page) => set({ currentPage: page }),
  setPersonas: (personas: Persona[]) => set({ personas }),

  loadPersona: (persona: 'ravi' | 'priya' | 'arjun') =>
    set((state) => {
      const personaNameMap = {
        ravi: 'Ravi',
        priya: 'Priya',
        arjun: 'Arjun',
      } as const;

      const selected = state.personas.find((p) => p.name.toLowerCase() === personaNameMap[persona].toLowerCase());

      if (!selected) {
        return { activePersona: persona };
      }

      const confidence = selected.confidence && selected.confidence.length === 2
        ? [selected.confidence[0], selected.confidence[1]] as [number, number]
        : [Math.max(300, selected.pulse_score - 30), Math.min(850, selected.pulse_score + 30)] as [number, number];

      const normalizedShap = Array.isArray(selected.shap_top3)
        ? selected.shap_top3
        : Object.values((selected.shap_top3 || {}) as Record<string, { name?: string; feature?: string; value: number; impact: number }>).map((item) => ({
            feature: item.feature || item.name || 'unknown_feature',
            value: item.value,
            impact: item.impact,
          }));

      const score: ScoreResult = {
        profile_id: selected.id,
        pulse_score: selected.pulse_score,
        confidence_interval: confidence,
        band: (selected.band as ScoreResult['band']) || 'fair',
        archetype: selected.archetype,
        dimensions: selected.dimensions,
        shap_top3: normalizedShap,
        explanation: `Demo persona loaded: ${selected.name}.`,
        actions: [
          { action: 'Make at least one UPI payment every 3 days', delta: 18, priority: 1 },
          { action: 'Keep monthly spend within 20% of last month', delta: 14, priority: 2 },
          { action: 'Build more reciprocal transfers with trusted contacts', delta: 11, priority: 3 },
        ],
        lender_memo: 'Demo profile memo. Upload a real statement for production-grade memo generation.',
      };

      return {
        activePersona: persona,
        profileId: selected.id,
        archetype: selected.archetype,
        score,
        currentPage: 'dashboard',
      };
    }),

  setSimulatorOverride: (dim: keyof DimensionScores, value: number) =>
    set((state) => ({
      simulatorOverrides: {
        ...state.simulatorOverrides,
        [dim]: value,
      },
    })),

  setSimulatedScore: (score: ScoreResult | null) => set({ simulatedScore: score }),

  resetSimulator: () =>
    set({
      simulatorOverrides: {},
      simulatedScore: null,
    }),

  reset: () =>
    set({
      profileId: null,
      archetype: null,
      transactions: [],
      dimensions: null,
      score: null,
      isLoading: false,
      isUploading: false,
      error: null,
      currentPage: 'upload',
      activePersona: null,
      simulatorOverrides: {},
      simulatedScore: null,
    }),
}));
