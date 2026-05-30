import { auditBundleUrl, reportPdfUrl, reportUrl } from '../api';
import type { Comparison, RunResult } from '../types';
import { currency, integerWithCommas, irr, kw, payback } from '../format';
import { recommendedIndex } from '../recommend';
import { Button, Card } from './ui';
import { CompareBars, MonthlyBars } from './charts';
import { DataSources } from './DataSources';
import { EngineModeBadge, WarningsList, dataSanityIssues } from './Warnings';

const ORIENTATION_NAMES: Record<string, string> = {
  N: 'North',
  NE: 'Northeast',
  E: 'East',
  SE: 'Southeast',
  S: 'South',
  SW: 'Southwest',
  W: 'West',
  NW: 'Northwest',
  H: 'Horizontal',
};

function StatTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="text-center">
      <div className="text-2xl font-bold text-ink">{value}</div>
      <div className="mt-1 text-xs font-semibold uppercase tracking-wide text-ink/60">
        {label}
      </div>
      {sub && <div className="mt-0.5 text-xs text-ink/40">{sub}</div>}
    </Card>
  );
}

function solarByOrientation(run: RunResult): Record<string, number> {
  const out: Record<string, number> = {};
  for (const w of run.windows) {
    const o = w.surface_name.split('_')[1] ?? '?';
    out[o] = (out[o] ?? 0) + w.annual_solar_transmitted_kwh;
  }
  return out;
}

function EndUseCard({ baseline, after }: { baseline: RunResult; after: RunResult }) {
  const b = baseline.annual_end_uses;
  const a = after.annual_end_uses;
  const rows = [
    { label: 'Cooling', before: b.cooling_elec_kwh, after: a.cooling_elec_kwh },
    { label: 'Heating', before: b.heating_elec_kwh, after: a.heating_elec_kwh },
    { label: 'Lighting', before: b.interior_lighting_kwh, after: a.interior_lighting_kwh },
    { label: 'Equipment', before: b.interior_equipment_kwh, after: a.interior_equipment_kwh },
    { label: 'Fans', before: b.fans_kwh, after: a.fans_kwh },
  ].filter((r) => r.before > 0 || r.after > 0);
  return (
    <Card>
      <h3 className="mb-1 font-semibold text-ink">Annual energy by end use</h3>
      <p className="mb-4 text-xs text-ink/50">
        Baseline vs. {after.scenario_label} (kWh/yr)
      </p>
      <CompareBars rows={rows} fmt={(n) => integerWithCommas(n)} />
    </Card>
  );
}

function SolarCard({ baseline, after }: { baseline: RunResult; after: RunResult }) {
  const bo = solarByOrientation(baseline);
  const ao = solarByOrientation(after);
  const order = ['S', 'SE', 'SW', 'E', 'W', 'NE', 'NW', 'N', 'H'];
  const rows = order
    .filter((o) => o in bo)
    .map((o) => ({ label: ORIENTATION_NAMES[o] ?? o, before: bo[o], after: ao[o] ?? 0 }));
  return (
    <Card>
      <h3 className="mb-1 font-semibold text-ink">Solar gain rejected by face</h3>
      <p className="mb-4 text-xs text-ink/50">
        Transmitted solar through glazing (kWh/yr)
      </p>
      <CompareBars rows={rows} fmt={(n) => integerWithCommas(n)} />
    </Card>
  );
}

function AppendixGCard({ comparison }: { comparison: Comparison }) {
  const a = comparison.appendix_g;
  if (!a) return null;
  return (
    <Card>
      <h3 className="mb-1 font-semibold text-ink">LEED PCI anchor</h3>
      <p className="mb-4 text-xs text-ink/50">
        ASHRAE 90.1-2019 Appendix G baseline (prescriptive U {a.window_u_factor.toFixed(2)} BTU/h·ft²·F,
        SHGC {a.window_shgc.toFixed(2)} per Table G3.4)
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-md bg-amber/10 px-3 py-2.5">
          <div className="text-2xl font-bold text-ink">
            {a.pct_savings_vs_code_baseline.toFixed(1)}%
          </div>
          <div className="text-xs font-semibold uppercase tracking-wide text-ink/60">
            Total electricity vs Appendix G
          </div>
        </div>
        <div className="rounded-md bg-amber/10 px-3 py-2.5">
          <div className="text-2xl font-bold text-ink">
            {a.cooling_pct_savings_vs_code_baseline.toFixed(1)}%
          </div>
          <div className="text-xs font-semibold uppercase tracking-wide text-ink/60">
            Cooling electricity vs Appendix G
          </div>
        </div>
      </div>
      <p className="mt-3 text-xs text-ink/50">
        These percentages anchor LEED EAc credit calculations. The audit
        bundle's CITATIONS.md records the exact prescriptive U/SHGC used.
      </p>
    </Card>
  );
}


function SavingsCard({ comparison }: { comparison: Comparison }) {
  const results = comparison.films;
  const max = Math.max(1, ...results.map((r) => r.delta_cost_usd_per_year));
  const recIdx = recommendedIndex(results);
  return (
    <Card>
      <h3 className="mb-4 font-semibold text-ink">Annual $ savings by scenario</h3>
      <div className="space-y-3">
        {results.map((r, i) => {
          const pct = Math.max(0, (r.delta_cost_usd_per_year / max) * 100);
          return (
            <div key={i}>
              <div className="mb-1 flex justify-between text-xs text-ink/70">
                <span className="font-medium">
                  {i === recIdx && (
                    <span className="mr-1 rounded bg-amber px-1 py-0.5 text-[9px] font-bold uppercase text-white">
                      Rec
                    </span>
                  )}
                  {r.scenario_label} · {r.film_sku}
                </span>
                <span className="font-semibold text-ink">
                  {currency(r.delta_cost_usd_per_year)}/yr
                </span>
              </div>
              <div className="h-5 w-full overflow-hidden rounded bg-neutralbg">
                <div
                  className={`h-full rounded ${i === recIdx ? 'bg-amber' : 'bg-ink/40'}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function Badge({ source }: { source: 'user' | 'default' }) {
  return source === 'user' ? (
    <span className="rounded bg-amber/20 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-amber-dark">
      measured
    </span>
  ) : (
    <span className="rounded bg-ink/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-ink/50">
      default
    </span>
  );
}

function AssumptionsCard({ comparison }: { comparison: Comparison }) {
  const b = comparison.building;
  if (!b) return null;
  const num = (n: number, d = 2) => (Number.isFinite(n) ? Number(n.toFixed(d)) : n);
  const rows: { label: string; value: string; key: string }[] = [
    { label: 'Cooling COP', value: String(num(b.cooling_cop)), key: 'cooling_cop' },
    { label: 'Heating COP', value: String(num(b.heating_cop)), key: 'heating_cop' },
    { label: 'HVAC system', value: b.hvac_system_type.replace(/_/g, ' '), key: 'hvac_system_type' },
    { label: 'Wall U', value: String(num(b.wall_u_factor, 3)), key: 'wall_u_factor' },
    { label: 'Wall area', value: `${integerWithCommas(b.wall_area_sf)} sf`, key: 'wall_area_sf' },
    { label: 'Roof type', value: b.roof_type.replace(/_/g, ' '), key: 'roof_type' },
    { label: 'Roof U', value: String(num(b.roof_u_factor, 3)), key: 'roof_u_factor' },
    { label: 'Roof absorptance', value: String(num(b.roof_absorptance)), key: 'roof_absorptance' },
    { label: 'Operating hrs/wk', value: String(num(b.operating_hours_per_week, 0)), key: 'operating_hours_per_week' },
    { label: 'Floors', value: String(b.num_floors), key: 'num_floors' },
  ];
  return (
    <Card>
      <h3 className="mb-1 font-semibold text-ink">Modeling assumptions</h3>
      <p className="mb-3 text-xs text-ink/50">
        As-built inputs drive the estimate; blanks use prototype / ASHRAE 90.1
        defaults.
      </p>
      <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
        {rows.map((r) => (
          <div key={r.key} className="flex items-center justify-between gap-2 border-b border-ink/5 pb-1.5">
            <dt className="text-xs text-ink/60">{r.label}</dt>
            <dd className="flex items-center gap-2 text-sm font-medium text-ink">
              <span className="capitalize">{r.value}</span>
              <Badge source={b.sources[r.key] === 'user' ? 'user' : 'default'} />
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

function ComparisonTable({ comparison }: { comparison: Comparison }) {
  const results = comparison.films;
  const recIdx = recommendedIndex(results);
  const cols = ['Scenario', 'ΔCooling', 'ΔHeating', 'ΔTotal', '$/yr', 'Project Cost', 'Payback', 'NPV 15yr', 'IRR', 'CO₂/yr'];
  return (
    <div className="overflow-x-auto rounded-md border border-ink/10">
      <table className="w-full text-sm">
        <thead className="bg-neutralbg text-left text-xs uppercase tracking-wide text-ink/60">
          <tr>
            {cols.map((c) => (
              <th key={c} className="whitespace-nowrap px-3 py-2">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => (
            <tr key={i} className={`border-t border-ink/10 ${i === recIdx ? 'bg-amber/10' : ''}`}>
              <td className="whitespace-nowrap px-3 py-2 font-medium text-ink">
                {i === recIdx && (
                  <span className="mr-1 rounded bg-amber px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">
                    Rec
                  </span>
                )}
                {r.scenario_label} <span className="text-ink/50">{r.film_sku}</span>
              </td>
              <td className="px-3 py-2">{integerWithCommas(r.delta_cooling_kwh)}</td>
              <td className="px-3 py-2">{integerWithCommas(r.delta_heating_kwh)}</td>
              <td className="px-3 py-2">{integerWithCommas(r.delta_total_kwh)}</td>
              <td className="px-3 py-2 font-medium">{currency(r.delta_cost_usd_per_year)}</td>
              <td className="px-3 py-2">{currency(r.project_cost_usd)}</td>
              <td className="px-3 py-2">{payback(r.simple_payback_years)}</td>
              <td className="px-3 py-2">{currency(r.npv_15yr_usd)}</td>
              <td className="px-3 py-2">{irr(r.irr_15yr_pct)}</td>
              <td className="px-3 py-2">{integerWithCommas(r.delta_co2_lb_per_year)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ResultsDashboard({
  comparison,
  jobId,
}: {
  comparison: Comparison;
  jobId: string;
}) {
  const results = comparison.films;
  const recIdx = recommendedIndex(results);
  const rec = recIdx >= 0 ? results[recIdx] : null;
  const recRun =
    comparison.film_runs.find((r) => r.scenario_label === rec?.scenario_label) ??
    comparison.film_runs[0];
  const sanityCount = dataSanityIssues(comparison).length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-ink">Results</h2>
          <EngineModeBadge engineMode={comparison.engine_mode} />
          {sanityCount > 0 && (
            <span className="rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-red-700">
              {sanityCount} data {sanityCount === 1 ? 'issue' : 'issues'}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <Button onClick={() => window.open(reportUrl(jobId), '_blank', 'noopener')}>
            Open Branded Report
          </Button>
          <Button
            variant="secondary"
            onClick={() => window.open(reportPdfUrl(jobId), '_blank', 'noopener')}
          >
            Download PDF
          </Button>
          <Button
            variant="secondary"
            onClick={() => window.open(auditBundleUrl(jobId), '_blank', 'noopener')}
          >
            Download Audit Bundle (.zip)
          </Button>
        </div>
      </div>

      <WarningsList comparison={comparison} />

      {rec ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile
            label="Annual savings"
            value={`${currency(rec.delta_cost_usd_per_year)}/yr`}
            sub={`${rec.scenario_label} · ${rec.film_sku}`}
          />
          <StatTile label="Simple payback" value={payback(rec.simple_payback_years)} />
          <StatTile label="Peak demand cut" value={kw(rec.delta_peak_kw)} />
          <StatTile
            label="CO₂ avoided"
            value={`${integerWithCommas(rec.delta_co2_lb_per_year)} lb`}
            sub="per year"
          />
        </div>
      ) : (
        <Card>
          <p className="text-sm text-ink/70">
            No scenario produced positive savings with a valid payback. Review the
            comparison below.
          </p>
        </Card>
      )}

      {recRun && (
        <div className="grid gap-6 lg:grid-cols-2">
          <EndUseCard baseline={comparison.baseline} after={recRun} />
          <SolarCard baseline={comparison.baseline} after={recRun} />
        </div>
      )}

      {rec?.monthly_cooling_savings_kwh && rec.monthly_cooling_savings_kwh.length === 12 && (
        <Card>
          <h3 className="mb-1 font-semibold text-ink">Monthly cooling savings</h3>
          <p className="mb-4 text-xs text-ink/50">
            {rec.scenario_label} · {rec.film_sku} — cooling kWh avoided by month
          </p>
          <MonthlyBars
            values={rec.monthly_cooling_savings_kwh}
            fmt={(n) => `${integerWithCommas(n)} kWh`}
          />
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <SavingsCard comparison={comparison} />
        <AssumptionsCard comparison={comparison} />
      </div>

      {comparison.appendix_g && <AppendixGCard comparison={comparison} />}

      <Card>
        <h3 className="mb-3 font-semibold text-ink">Scenario comparison</h3>
        <ComparisonTable comparison={comparison} />
      </Card>

      <DataSources />
    </div>
  );
}
