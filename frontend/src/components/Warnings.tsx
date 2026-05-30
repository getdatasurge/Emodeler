import type { Comparison, RunResult } from '../types';

interface ClassifiedWarning {
  text: string;
  severity: 'error' | 'warning' | 'info';
}

function classify(w: string): ClassifiedWarning {
  const lower = w.toLowerCase();
  if (
    lower.includes('not bid-grade') ||
    lower.includes('not for bid') ||
    lower.includes('energyplus run failed') ||
    lower.includes('exited') ||
    lower.includes('severe')
  ) {
    return { text: w, severity: 'error' };
  }
  if (
    lower.includes('preliminary estimate') ||
    lower.includes('analytical estimate') ||
    lower.includes('not yet provisioned')
  ) {
    return { text: w, severity: 'warning' };
  }
  // Informational (scale factor, methodology breadcrumbs).
  return { text: w, severity: 'info' };
}

// Pull warnings from every run + the comparison; dedupe; classify.
function collectWarnings(comparison: Comparison): ClassifiedWarning[] {
  const seen = new Set<string>();
  const out: ClassifiedWarning[] = [];
  const sources: (string[] | undefined)[] = [
    comparison.warnings,
    comparison.baseline?.warnings,
    ...(comparison.film_runs ?? []).map((r: RunResult) => r.warnings),
    comparison.appendix_g?.run?.warnings,
  ];
  for (const src of sources) {
    if (!src) continue;
    for (const w of src) {
      if (!w || seen.has(w)) continue;
      seen.add(w);
      out.push(classify(w));
    }
  }
  // Errors first, then warnings, then info.
  const order = { error: 0, warning: 1, info: 2 } as const;
  out.sort((a, b) => order[a.severity] - order[b.severity]);
  return out;
}

const styles = {
  error: 'border-red-300 bg-red-50 text-red-900',
  warning: 'border-amber-dark/30 bg-amber/15 text-ink',
  info: 'border-ink/10 bg-ink/5 text-ink',
} as const;

// Data-sanity heuristics: things that almost always mean a parser miss /
// bad input, not a real result. Surface as a single error banner so a user
// doesn't quote $0 savings as if they were real.
export function dataSanityIssues(comparison: Comparison): string[] {
  const issues: string[] = [];
  const baseline = comparison.baseline;
  if (baseline && baseline.annual_end_uses) {
    const eu = baseline.annual_end_uses;
    if (eu.cooling_elec_kwh === 0 && eu.heating_elec_kwh === 0) {
      issues.push(
        'Baseline cooling AND heating are zero — almost certainly the eplustbl.csv parser missed the End Uses table. The dollar savings will be invalid.',
      );
    }
  }
  if (comparison.films && comparison.films.length > 0) {
    const allZero = comparison.films.every(
      (f) => f.delta_total_kwh === 0 && f.delta_cost_usd_per_year === 0,
    );
    if (allZero) {
      issues.push(
        'Every film scenario reports zero delta vs baseline. The IDF mutation likely did not bind to any windows — check Glazing setup and per-face base_glazing_id.',
      );
    }
  }
  return issues;
}

export function WarningsList({ comparison }: { comparison: Comparison }) {
  const warnings = collectWarnings(comparison);
  const dataIssues = dataSanityIssues(comparison);
  if (warnings.length === 0 && dataIssues.length === 0) return null;

  return (
    <div className="space-y-2">
      {dataIssues.map((msg, i) => (
        <div
          key={`d${i}`}
          className={`rounded-md border px-4 py-3 text-sm ${styles.error}`}
        >
          <span className="mr-1.5 inline-block rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-red-700">
            data check
          </span>
          {msg}
        </div>
      ))}
      {warnings.map((w, i) => (
        <div
          key={`w${i}`}
          className={`rounded-md border px-4 py-3 text-sm ${styles[w.severity]}`}
        >
          <span
            className={`mr-1.5 inline-block rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
              w.severity === 'error'
                ? 'bg-red-100 text-red-700'
                : w.severity === 'warning'
                ? 'bg-amber/30 text-amber-dark'
                : 'bg-ink/10 text-ink/60'
            }`}
          >
            {w.severity}
          </span>
          {w.text}
        </div>
      ))}
    </div>
  );
}

export function EngineModeBadge({ engineMode }: { engineMode: string }) {
  const live = engineMode === 'energyplus';
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide ${
        live ? 'bg-green-100 text-green-800' : 'bg-amber/20 text-amber-dark'
      }`}
    >
      <span className={`h-2 w-2 rounded-full ${live ? 'bg-green-500' : 'bg-amber-dark'}`} />
      {live ? 'EnergyPlus' : 'Analytical estimate'}
    </span>
  );
}
