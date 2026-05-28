import { auditBundleUrl, reportUrl } from '../api';
import type { JobCompleted } from '../types';
import { currency, integerWithCommas, irr, kw, payback } from '../format';
import { recommendedIndex } from '../recommend';
import { Button, Card } from './ui';

function StatTile({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
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

// Simple CSS bar chart comparing scenarios by annual $ savings.
function SavingsBars({ job }: { job: JobCompleted }) {
  const results = job.scenario_results;
  const max = Math.max(1, ...results.map((r) => r.delta_cost_usd_per_year));
  const recIdx = recommendedIndex(results);
  return (
    <div className="space-y-3">
      {results.map((r, i) => {
        const pct = Math.max(0, (r.delta_cost_usd_per_year / max) * 100);
        return (
          <div key={i}>
            <div className="mb-1 flex justify-between text-xs text-ink/70">
              <span className="font-medium">
                {r.scenario_label} · {r.film_sku}
              </span>
              <span>{currency(r.delta_cost_usd_per_year)}/yr</span>
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
  );
}

function ComparisonTable({ job }: { job: JobCompleted }) {
  const results = job.scenario_results;
  const recIdx = recommendedIndex(results);
  const cols: { key: string; label: string }[] = [
    { key: 'scenario', label: 'Scenario' },
    { key: 'cool', label: 'ΔCooling kWh' },
    { key: 'heat', label: 'ΔHeating kWh' },
    { key: 'total', label: 'ΔTotal kWh' },
    { key: 'cost', label: '$/yr' },
    { key: 'projcost', label: 'Project Cost' },
    { key: 'payback', label: 'Payback' },
    { key: 'npv', label: 'NPV 15yr' },
    { key: 'irr', label: 'IRR%' },
    { key: 'co2', label: 'CO2/yr lb' },
  ];
  return (
    <div className="overflow-x-auto rounded-md border border-ink/10">
      <table className="w-full text-sm">
        <thead className="bg-neutralbg text-left text-xs uppercase tracking-wide text-ink/60">
          <tr>
            {cols.map((c) => (
              <th key={c.key} className="whitespace-nowrap px-3 py-2">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => (
            <tr
              key={i}
              className={`border-t border-ink/10 ${i === recIdx ? 'bg-amber/10' : ''}`}
            >
              <td className="whitespace-nowrap px-3 py-2 font-medium text-ink">
                {i === recIdx && (
                  <span className="mr-1 rounded bg-amber px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">
                    Rec
                  </span>
                )}
                {r.scenario_label}{' '}
                <span className="text-ink/50">{r.film_sku}</span>
              </td>
              <td className="px-3 py-2">
                {integerWithCommas(r.delta_cooling_kwh)}
              </td>
              <td className="px-3 py-2">
                {integerWithCommas(r.delta_heating_kwh)}
              </td>
              <td className="px-3 py-2">
                {integerWithCommas(r.delta_total_kwh)}
              </td>
              <td className="px-3 py-2">
                {currency(r.delta_cost_usd_per_year)}
              </td>
              <td className="px-3 py-2">{currency(r.project_cost_usd)}</td>
              <td className="px-3 py-2">{payback(r.simple_payback_years)}</td>
              <td className="px-3 py-2">{currency(r.npv_15yr_usd)}</td>
              <td className="px-3 py-2">{irr(r.irr_15yr_pct)}</td>
              <td className="px-3 py-2">
                {integerWithCommas(r.delta_co2_lb_per_year)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ResultsDashboard({ job }: { job: JobCompleted }) {
  const results = job.scenario_results;
  const recIdx = recommendedIndex(results);
  const rec = recIdx >= 0 ? results[recIdx] : null;
  const showPreliminary =
    (job.warnings && job.warnings.length > 0) ||
    job.engine_mode !== 'energyplus';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-ink">Results</h2>
        <div className="flex gap-2">
          <a href={reportUrl(job.job_id)} target="_blank" rel="noreferrer">
            <Button>Open Branded Report</Button>
          </a>
          <a href={auditBundleUrl(job.job_id)}>
            <Button variant="secondary">Download Audit Bundle (.zip)</Button>
          </a>
        </div>
      </div>

      {showPreliminary && (
        <div className="rounded-md border border-amber-dark/30 bg-amber/15 px-4 py-3 text-sm text-ink">
          <span className="font-semibold text-amber-dark">
            Preliminary estimate.
          </span>{' '}
          {job.warnings && job.warnings.length > 0
            ? job.warnings[0]
            : 'These results were not produced by EnergyPlus and are not valid for bids.'}
        </div>
      )}

      {rec ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile
            label="Annual savings"
            value={`${currency(rec.delta_cost_usd_per_year)}/yr`}
            sub={`${rec.scenario_label} · ${rec.film_sku}`}
          />
          <StatTile
            label="Simple payback"
            value={payback(rec.simple_payback_years)}
          />
          <StatTile
            label="Peak demand cut"
            value={kw(rec.delta_peak_kw)}
          />
          <StatTile
            label="CO2 avoided"
            value={`${integerWithCommas(rec.delta_co2_lb_per_year)} lb`}
            sub="per year"
          />
        </div>
      ) : (
        <Card>
          <p className="text-sm text-ink/70">
            No scenario produced positive savings with a valid payback. Review
            the comparison below.
          </p>
        </Card>
      )}

      <Card>
        <h3 className="mb-3 font-semibold text-ink">Scenario comparison</h3>
        <ComparisonTable job={job} />
      </Card>

      <Card>
        <h3 className="mb-3 font-semibold text-ink">
          Annual savings by scenario
        </h3>
        <SavingsBars job={job} />
      </Card>
    </div>
  );
}
