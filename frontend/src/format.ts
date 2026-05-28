// Data-formatting helpers per the spec rules.
// simple_payback_years and irr_15yr_pct use -1 as an "n/a" sentinel.

const NA = 'n/a';

export function currency(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return NA;
  const sign = value < 0 ? '-' : '';
  const abs = Math.abs(value);
  return `${sign}$${abs.toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}

// kWh / CO2: thousands separators, no decimals (deltas can be negative).
export function integerWithCommas(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return NA;
  return Math.round(value).toLocaleString('en-US');
}

// Payback: 1 decimal + " yr"; -1 sentinel -> n/a.
export function payback(years: number | null | undefined): string {
  if (years == null || Number.isNaN(years) || years === -1) return NA;
  return `${years.toFixed(1)} yr`;
}

// IRR: 1 decimal + "%"; -1 sentinel -> n/a.
export function irr(pct: number | null | undefined): string {
  if (pct == null || Number.isNaN(pct) || pct === -1) return NA;
  return `${pct.toFixed(1)}%`;
}

// Peak demand kW: 1 decimal.
export function kw(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return NA;
  return `${value.toFixed(1)} kW`;
}
