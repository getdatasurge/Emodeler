import { useState } from 'react';

// Dismissible warning bar shown when EnergyPlus is unavailable (preliminary
// estimates, not for bids).
export function EstimateBanner({ notice }: { notice: string }) {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;
  return (
    <div className="border-b border-amber-dark/30 bg-amber/15">
      <div className="mx-auto flex max-w-6xl items-start justify-between gap-4 px-6 py-2.5">
        <p className="text-sm text-ink">
          <span className="font-semibold text-amber-dark">
            Preliminary estimate.
          </span>{' '}
          {notice}
        </p>
        <button
          onClick={() => setDismissed(true)}
          className="shrink-0 rounded px-2 text-lg leading-none text-ink/50 hover:text-ink"
          aria-label="Dismiss"
        >
          &times;
        </button>
      </div>
    </div>
  );
}
