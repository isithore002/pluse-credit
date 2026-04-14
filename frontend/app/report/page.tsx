'use client';

import { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { apiService } from '@/lib/api';
import { usePulseCreditStore } from '@/lib/store';

function ReportPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const store = usePulseCreditStore();
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const queryProfileId = searchParams.get('profile_id');
  const profileId = queryProfileId || store.profileId || store.score?.profile_id || '';

  const downloadReport = async () => {
    if (!profileId) {
      setError('Profile id is missing. Score a profile first.');
      return;
    }

    setIsDownloading(true);
    setError(null);

    try {
      const blob = await apiService.getReport(profileId);
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `pulsecredit-report-${profileId}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(`Report download failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="space-y-8 py-8">
      <section>
        <h2 className="text-3xl font-bold text-white">Lender Report</h2>
        <p className="mt-2 text-slate-400">Generate and download a PDF memo for underwriting.</p>
      </section>

      <section className="card">
        <p className="text-slate-300">Profile: {profileId || 'Not available'}</p>

        <div className="mt-6 flex gap-3">
          <button className="btn-primary" onClick={downloadReport} disabled={isDownloading}>
            {isDownloading ? 'Generating PDF...' : 'Download PDF'}
          </button>
          <button className="btn-secondary" onClick={() => router.push('/dashboard')}>
            Back To Dashboard
          </button>
        </div>

        {error && <div className="mt-4 rounded border border-red-700 bg-red-900/20 p-3 text-red-200">{error}</div>}
      </section>
    </div>
  );
}

export default function ReportPage() {
  return (
    <Suspense fallback={<div className="py-8 text-slate-300">Loading report...</div>}>
      <ReportPageContent />
    </Suspense>
  );
}
