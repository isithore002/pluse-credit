'use client';

import { useDropzone } from 'react-dropzone';

interface UploadZoneProps {
  isUploading: boolean;
  isDragActive?: boolean;
  pdfPassword: string;
  onPasswordChange: (value: string) => void;
  onDrop: (files: File[]) => void;
}

export default function UploadZone({
  isUploading,
  pdfPassword,
  onPasswordChange,
  onDrop,
}: UploadZoneProps) {
  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    noClick: true,
    accept: {
      'application/pdf': ['.pdf'],
      'text/csv': ['.csv'],
    },
    onDrop,
  });

  return (
    <div
      {...getRootProps()}
      className={`rounded-lg border-2 border-dashed px-8 py-16 text-center transition-all ${
        isDragActive
          ? 'border-purple-400 bg-purple-900/20'
          : 'border-slate-600 bg-slate-900/30 hover:border-slate-500'
      }`}
    >
      <input {...getInputProps()} />

      {isUploading ? (
        <div className="flex flex-col items-center">
          <div className="h-12 w-12 animate-spin rounded-full border-4 border-slate-600 border-t-purple-500"></div>
          <p className="mt-4 text-slate-300">Processing statement...</p>
        </div>
      ) : (
        <>
          <svg className="mx-auto h-16 w-16 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <p className="mt-4 text-lg text-slate-300">
            {isDragActive ? 'Drop your statement here' : 'Drag and drop your UPI statement'}
          </p>
          <p className="mt-2 text-sm text-slate-400">PDF or CSV • HDFC, SBI, ICICI, Kotak supported</p>
          <div className="mx-auto mt-4 max-w-sm">
            <input
              type="password"
              value={pdfPassword}
              onChange={(e) => onPasswordChange(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              onKeyDown={(e) => e.stopPropagation()}
              placeholder="PDF password (optional)"
              className="w-full rounded-md border border-slate-600 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 placeholder-slate-400 focus:border-purple-500 focus:outline-none"
            />
          </div>
          <button type="button" onClick={open} className="btn-primary mt-6">
            Select File
          </button>
        </>
      )}
    </div>
  );
}
