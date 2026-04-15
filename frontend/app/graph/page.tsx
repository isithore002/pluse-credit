'use client';

import { useRouter } from 'next/navigation';
import { usePulseCreditStore } from '@/lib/store';
import SocialGraph from '@/components/SocialGraph';

export default function GraphPage() {
  const router = useRouter();
  const store = usePulseCreditStore();

  return (
    <div className="space-y-8 py-8">
      <section>
        <h2 className="text-3xl font-bold text-white">Social Trust Graph</h2>
        <p className="mt-2 text-slate-400">
          Contact network derived from transaction counterparties and interaction frequency.
        </p>
      </section>

      <section className="card">
        <SocialGraph transactions={store.transactions} />
      </section>

      <section className="flex gap-3">
        <button className="btn-secondary" onClick={() => router.push('/dashboard')}>
          Back To Dashboard
        </button>
      </section>
    </div>
  );
}
