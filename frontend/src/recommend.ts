import type { ScenarioResult } from './types';

// Recommended = the scenario with positive annual $ savings and the lowest
// (valid, non -1 sentinel) simple payback. Returns the index, or -1 if none.
export function recommendedIndex(results: ScenarioResult[]): number {
  let best = -1;
  let bestPayback = Infinity;
  results.forEach((r, i) => {
    const hasSavings = r.delta_cost_usd_per_year > 0;
    const validPayback = r.simple_payback_years > 0; // -1 sentinel excluded
    if (hasSavings && validPayback && r.simple_payback_years < bestPayback) {
      bestPayback = r.simple_payback_years;
      best = i;
    }
  });
  return best;
}
