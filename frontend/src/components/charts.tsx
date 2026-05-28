// Dependency-free chart primitives (Tailwind divs, no charting lib).

export function MiniBar({
  value,
  max,
  className = 'bg-amber',
}: {
  value: number;
  max: number;
  className?: string;
}) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <div className="h-2.5 w-full overflow-hidden rounded-full bg-neutralbg">
      <div className={`h-full rounded-full ${className}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

const MONTHS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];

// 12 vertical bars (Jan..Dec).
export function MonthlyBars({
  values,
  fmt,
}: {
  values: number[];
  fmt: (n: number) => string;
}) {
  const max = Math.max(1, ...values.map((v) => Math.abs(v)));
  return (
    <div className="flex h-36 items-end gap-1.5">
      {values.map((v, i) => (
        <div key={i} className="flex flex-1 flex-col items-center justify-end">
          <div
            className="w-full rounded-t bg-amber"
            style={{ height: `${Math.max(2, (Math.abs(v) / max) * 100)}%` }}
            title={fmt(v)}
          />
          <span className="mt-1 text-[10px] text-ink/50">{MONTHS[i]}</span>
        </div>
      ))}
    </div>
  );
}

export interface CompareRow {
  label: string;
  before: number;
  after: number;
}

// Baseline (ink) vs after-film (amber) paired bars, with the % reduction.
export function CompareBars({
  rows,
  fmt,
}: {
  rows: CompareRow[];
  fmt: (n: number) => string;
}) {
  const max = Math.max(1, ...rows.map((r) => Math.max(r.before, r.after)));
  return (
    <div className="space-y-3.5">
      {rows.map((r) => {
        const pct = r.before > 0 ? Math.round((1 - r.after / r.before) * 100) : 0;
        return (
          <div key={r.label}>
            <div className="mb-1 flex items-baseline justify-between text-xs">
              <span className="font-medium text-ink">{r.label}</span>
              <span className="text-ink/60">
                {fmt(r.before)} <span className="text-ink/30">→</span>{' '}
                <span className="font-semibold text-ink">{fmt(r.after)}</span>
                {pct > 0 && (
                  <span className="ml-1.5 font-semibold text-green-700">↓{pct}%</span>
                )}
              </span>
            </div>
            <div className="space-y-1">
              <MiniBar value={r.before} max={max} className="bg-ink/25" />
              <MiniBar value={r.after} max={max} className="bg-amber" />
            </div>
          </div>
        );
      })}
      <div className="flex gap-4 pt-1 text-[11px] text-ink/50">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-3 rounded-sm bg-ink/25" /> Baseline
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-3 rounded-sm bg-amber" /> After film
        </span>
      </div>
    </div>
  );
}
