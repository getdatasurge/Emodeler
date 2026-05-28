import { useEffect, useState } from 'react';
import { api } from '../api';
import type { Film, Pairing } from '../types';
import { Button, Label, Select, TextInput } from './ui';

export interface CandidateDraft {
  label: string;
  film_sku: string;
  installed_cost_usd: string;
}

// One film candidate card with a pairing preview against the base glazing.
function CandidateCard({
  index,
  draft,
  films,
  baseGlazingId,
  onChange,
  onRemove,
  removable,
}: {
  index: number;
  draft: CandidateDraft;
  films: Film[];
  baseGlazingId: string | null;
  onChange: (d: CandidateDraft) => void;
  onRemove: () => void;
  removable: boolean;
}) {
  const [pairing, setPairing] = useState<Pairing | null>(null);
  const [pairingError, setPairingError] = useState<string | null>(null);

  // When both a film SKU and the first face base glazing are known, fetch the
  // computed applied properties for the pairing.
  useEffect(() => {
    let active = true;
    setPairing(null);
    setPairingError(null);
    if (!draft.film_sku || !baseGlazingId) return;
    api
      .pairing(draft.film_sku, baseGlazingId)
      .then((p) => active && setPairing(p))
      .catch((e) => active && setPairingError((e as Error).message));
    return () => {
      active = false;
    };
  }, [draft.film_sku, baseGlazingId]);

  const selectedFilm = films.find((f) => f.sku === draft.film_sku);

  // Group films by product line for the dropdown.
  const lines = Array.from(new Set(films.map((f) => f.product_line)));

  return (
    <div className="rounded-md border border-ink/15 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-ink/50">
          Candidate {index + 1}
        </span>
        {removable && (
          <button
            onClick={onRemove}
            className="text-xs text-ink/50 hover:text-red-600"
          >
            Remove
          </button>
        )}
      </div>

      <div className="grid gap-3">
        <div>
          <Label>Label</Label>
          <TextInput
            value={draft.label}
            onChange={(e) => onChange({ ...draft, label: e.target.value })}
            placeholder="Good / Better / Best"
          />
        </div>
        <div>
          <Label>Film (SKU)</Label>
          <Select
            value={draft.film_sku}
            onChange={(e) => onChange({ ...draft, film_sku: e.target.value })}
          >
            <option value="">Select a film…</option>
            {lines.map((line) => (
              <optgroup key={line} label={line}>
                {films
                  .filter((f) => f.product_line === line)
                  .map((f) => (
                    <option key={f.sku} value={f.sku}>
                      {f.display_name} — VLT {f.tvis_pct}% · SHGC{' '}
                      {f.shgc_on_dbl_clear}
                    </option>
                  ))}
              </optgroup>
            ))}
          </Select>
        </div>
        <div>
          <Label>Installed cost ($)</Label>
          <TextInput
            type="number"
            value={draft.installed_cost_usd}
            onChange={(e) =>
              onChange({ ...draft, installed_cost_usd: e.target.value })
            }
            placeholder="0"
          />
        </div>
      </div>

      {selectedFilm && (
        <div className="mt-3 rounded bg-neutralbg p-3 text-xs text-ink/70">
          <div className="font-medium text-ink">
            {selectedFilm.product_line} · warranty {selectedFilm.warranty_yrs} yr
            · list ${selectedFilm.list_price_per_sqft}/sf
          </div>
          {pairingError && (
            <div className="mt-1 text-red-600">{pairingError}</div>
          )}
          {pairing && (
            <div className="mt-2 grid grid-cols-3 gap-2 text-center">
              <PairStat label="Applied SHGC" value={pairing.shgc} />
              <PairStat
                label="U (Btu/h·ft²·F)"
                value={pairing.u_btu_h_ft2_F}
              />
              <PairStat label="VT" value={pairing.vt} />
            </div>
          )}
          {!pairing && !pairingError && baseGlazingId && (
            <div className="mt-1 italic text-ink/40">Computing pairing…</div>
          )}
          {!baseGlazingId && (
            <div className="mt-1 italic text-ink/40">
              Add a glazing face to see the applied pairing.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PairStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded bg-white px-2 py-1.5">
      <div className="text-sm font-semibold text-ink">{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-ink/50">
        {label}
      </div>
    </div>
  );
}

export function FilmCandidates({
  films,
  baseGlazingId,
  candidates,
  onChange,
}: {
  films: Film[];
  baseGlazingId: string | null;
  candidates: CandidateDraft[];
  onChange: (c: CandidateDraft[]) => void;
}) {
  function update(i: number, d: CandidateDraft) {
    onChange(candidates.map((c, idx) => (idx === i ? d : c)));
  }
  function remove(i: number) {
    onChange(candidates.filter((_, idx) => idx !== i));
  }
  function add() {
    if (candidates.length >= 3) return;
    onChange([
      ...candidates,
      { label: '', film_sku: '', installed_cost_usd: '' },
    ]);
  }

  return (
    <div>
      <div className="grid gap-4 lg:grid-cols-3">
        {candidates.map((c, i) => (
          <CandidateCard
            key={i}
            index={i}
            draft={c}
            films={films}
            baseGlazingId={baseGlazingId}
            onChange={(d) => update(i, d)}
            onRemove={() => remove(i)}
            removable={candidates.length > 1}
          />
        ))}
      </div>
      {candidates.length < 3 && (
        <div className="mt-4">
          <Button variant="secondary" onClick={add}>
            + Add candidate ({candidates.length}/3)
          </Button>
        </div>
      )}
    </div>
  );
}
