'use client';

interface LenderReportProps {
  profileId: string;
  isDownloading: boolean;
  error: string | null;
  onDownload: () => void;
  onBack: () => void;
}

export default function LenderReport({
  profileId,
  isDownloading,
  error,
  onDownload,
  onBack,
}: LenderReportProps) {
  return (
    <section className="card">
      <p className="text-slate-300">Profile: {profileId || 'Not available'}</p>

      <div className="mt-6 flex gap-3">
        <button className="btn-primary" onClick={onDownload} disabled={isDownloading}>
          {isDownloading ? 'Generating PDF...' : 'Download PDF'}
        </button>
        <button className="btn-secondary" onClick={onBack}>
          Back To Dashboard
        </button>
      </div>

      {error && <div className="mt-4 rounded border border-red-700 bg-red-900/20 p-3 text-red-200">{error}</div>}
    </section>
  );
}
