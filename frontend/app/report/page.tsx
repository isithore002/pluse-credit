'use client';

import { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { apiService } from '@/lib/api';
import { usePulseCreditStore } from '@/lib/store';
import LenderReport from '@/components/LenderReport';

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

      <LenderReport
        profileId={profileId}
        isDownloading={isDownloading}
        error={error}
        onDownload={downloadReport}
        onBack={() => router.push('/dashboard')}
      />
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
