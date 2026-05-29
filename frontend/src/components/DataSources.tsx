import { useEffect, useState } from 'react';
import { api } from '../api';
import type { Meta } from '../types';
import { Card } from './ui';

function SourceRow({
  label,
  detail,
  live,
}: {
  label: string;
  detail: string;
  live: boolean;
}) {
  return (
    <div className="flex items-center justify-between border-b border-ink/5 py-1.5">
      <div>
        <span className="text-sm font-medium text-ink">{label}</span>{' '}
        <span className="text-xs text-ink/50">{detail}</span>
      </div>
      <span
        className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
          live ? 'bg-green-100 text-green-800' : 'bg-ink/10 text-ink/50'
        }`}
      >
        {live ? 'Live' : 'Bundled'}
      </span>
    </div>
  );
}

// Shows which open-data integrations are answering live vs. from packaged
// offline data, so provenance is visible without reading /api/meta.
export function DataSources() {
  const [meta, setMeta] = useState<Meta | null>(null);
  useEffect(() => {
    api.meta().then(setMeta).catch(() => {});
  }, []);
  if (!meta) return null;
  return (
    <Card>
      <h3 className="mb-1 font-semibold text-ink">Data sources</h3>
      <p className="mb-3 text-xs text-ink/50">
        Live = queried per project from the upstream API; bundled = packaged
        offline reference data.
      </p>
      <SourceRow label="Solar / weather" detail="NREL NSRDB · PVWatts v8" live={meta.nrel_live} />
      <SourceRow label="Utility rates" detail="OpenEI URDB" live={meta.nrel_live} />
      <SourceRow label="Glazing optics" detail="LBNL IGSDB" live={meta.igsdb_live} />
      <SourceRow label="Carbon factors" detail="EPA eGRID 2023 (reference set)" live={false} />
      <SourceRow
        label="Engine"
        detail={meta.engine_mode === 'energyplus' ? 'EnergyPlus 22.1' : 'Analytical estimate'}
        live={meta.energyplus_available}
      />
      {!meta.nrel_live && (
        <p className="mt-3 text-xs text-ink/50">
          Set a free <span className="font-medium">NREL_API_KEY</span>{' '}
          (developer.nrel.gov) to switch solar + utility to live;{' '}
          <span className="font-medium">IGSDB_API_TOKEN</span> for live glazing optics.
        </p>
      )}
    </Card>
  );
}
