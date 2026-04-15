'use client';

// frontend/app/page.tsx - Landing page with upload and demo personas

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import axios from 'axios';
import { usePulseCreditStore } from '@/lib/store';
import { apiService } from '@/lib/api';
import UploadZone from '@/components/UploadZone';

export default function Home() {
  const router = useRouter();
  const store = usePulseCreditStore();
  const [hasBackend, setHasBackend] = useState(true);
  const [pdfPassword, setPdfPassword] = useState('');

  useEffect(() => {
    // Check backend health
    const checkHealth = async () => {
      try {
        await apiService.healthCheck();
        setHasBackend(true);
      } catch {
        setHasBackend(false);
      }
    };

    checkHealth();

    // Load demo personas
    const loadPersonas = async () => {
      try {
        const personas = await apiService.getDemoPersonas();
        store.setPersonas(personas);
      } catch (error) {
        console.log('Demo personas not available yet');
      }
    };

    loadPersonas();
  }, []);

  const handleDrop = async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    const file = acceptedFiles[0];
    store.setUploading(true);

    try {
      const isPdf = file.name.toLowerCase().endsWith('.pdf');
      const result = await apiService.parseStatement(file, 'HDFC', isPdf ? pdfPassword : '');
      store.setProfileId(result.profile_id);
      store.setTransactions(result.transactions);

      // Auto-compute score
      store.setLoading(true);
      const scoreResult = await apiService.computeScore(
        result.profile_id,
        result.transactions
      );
      store.setScore(scoreResult);

      router.push('/dashboard');
    } catch (error) {
      let message = 'Unknown error';
      if (axios.isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        message = detail || error.message;
      } else if (error instanceof Error) {
        message = error.message;
      }
      store.setError(`Upload failed: ${message}`);
    } finally {
      store.setUploading(false);
      store.setLoading(false);
    }
  };

  const handleDemoPersona = async (personaKey: 'ravi' | 'priya' | 'arjun') => {
    store.loadPersona(personaKey);
    router.push('/dashboard');
  };

  return (
    <div className="space-y-12 py-12">
      {/* Hero section */}
      <section className="text-center">
        <h2 className="text-5xl font-bold text-white">
          Your Credit Score, <span className="text-gradient">Reimagined</span>
        </h2>
        <p className="mt-4 text-xl text-slate-300">
          Behavioral credit scoring for India's 350M credit-invisible population
        </p>
      </section>

      {/* Backend Status */}
      {!hasBackend && (
        <div className="rounded-lg border border-yellow-600 bg-yellow-900/20 p-4 text-yellow-200">
          ⚠ Backend API not running. To start: <code>cd backend && python -m uvicorn main:app --reload</code>
        </div>
      )}

      {/* Upload Zone */}
      <section className="card">
        <h3 className="mb-6 text-2xl font-bold text-white">Upload Your Statement</h3>

        <UploadZone
          isUploading={store.isUploading}
          pdfPassword={pdfPassword}
          onPasswordChange={setPdfPassword}
          onDrop={handleDrop}
        />

        {store.error && (
          <div className="mt-4 rounded-lg border border-red-600 bg-red-900/20 p-4 text-red-200">
            {store.error}
          </div>
        )}
      </section>

      {/* Demo Personas */}
      <section className="card">
        <h3 className="mb-6 text-2xl font-bold text-white">Try Demo Personas</h3>

        <div className="grid gap-6 md:grid-cols-3">
          {[
            {
              key: 'ravi' as const,
              name: 'Ravi',
              archetype: 'Engineering Student',
              description: 'Daily ₹50 canteen, strong rhythm, weak velocity',
              score: 612,
            },
            {
              key: 'priya' as const,
              name: 'Priya',
              archetype: 'Swiggy Delivery Partner',
              description: 'Erratic earnings, high spend volatility',
              score: 571,
            },
            {
              key: 'arjun' as const,
              name: 'Arjun',
              archetype: 'Freelancer (Improving)',
              description: '3-month improving trajectory to near-excellent',
              score: 701,
            },
          ].map((persona) => (
            <button
              key={persona.key}
              onClick={() => handleDemoPersona(persona.key)}
              className="rounded-lg border border-slate-600 bg-slate-800 p-6 text-left transition-all hover:border-purple-500 hover:bg-slate-800/80"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h4 className="text-xl font-bold text-white">{persona.name}</h4>
                  <p className="text-sm text-purple-400">{persona.archetype}</p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold text-gradient">{persona.score}</p>
                  <p className="text-xs text-slate-400">/850</p>
                </div>
              </div>
              <p className="mt-4 text-sm text-slate-300">{persona.description}</p>
            </button>
          ))}
        </div>
      </section>

      {/* Info cards */}
      <section className="grid gap-6 md:grid-cols-2">
        <div className="card">
          <h4 className="flex items-center text-lg font-semibold text-white">
            <span className="mr-3 flex h-8 w-8 items-center justify-center rounded-lg bg-purple-500/20 text-purple-400">
              📊
            </span>
            6 Behavioral Dimensions
          </h4>
          <ul className="mt-4 space-y-2 text-sm text-slate-300">
            <li>✓ Payment Rhythm</li>
            <li>✓ Merchant Consistency</li>
            <li>✓ Social Trust</li>
            <li>✓ Calendar Alignment</li>
            <li>✓ Velocity Stability</li>
            <li>✓ NLP Intent</li>
          </ul>
        </div>

        <div className="card">
          <h4 className="flex items-center text-lg font-semibold text-white">
            <span className="mr-3 flex h-8 w-8 items-center justify-center rounded-lg bg-pink-500/20 text-pink-400">
                🤖
            </span>
            ML-Powered Scoring
          </h4>
          <ul className="mt-4 space-y-2 text-sm text-slate-300">
            <li>✓ XGBoost Ensemble (60%)</li>
            <li>✓ PyTorch Autoencoder (25%)</li>
            <li>✓ Heuristic Rules (15%)</li>
            <li>✓ SHAP Explainability</li>
            <li>✓ Gemini Flash LLM</li>
            <li>✓ 300-850 Score Range</li>
          </ul>
        </div>
      </section>
    </div>
  );
}
