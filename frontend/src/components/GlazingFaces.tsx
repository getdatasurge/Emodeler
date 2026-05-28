import { useState } from 'react';
import { api } from '../api';
import type { BaseGlazing, Project } from '../types';
import { Button, ErrorBox, Label, Select, TextInput } from './ui';

const ORIENTATIONS = ['N', 'S', 'E', 'W', 'H'];

export function GlazingFaces({
  project,
  baseGlazings,
  onProjectUpdate,
}: {
  project: Project;
  baseGlazings: BaseGlazing[];
  onProjectUpdate: (p: Project) => void;
}) {
  const [orientation, setOrientation] = useState('S');
  const [area, setArea] = useState('');
  const [baseGlazingId, setBaseGlazingId] = useState(
    baseGlazings[0]?.id ?? '',
  );
  const [count, setCount] = useState('1');
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const glazingName = (id: string) =>
    baseGlazings.find((g) => g.id === id)?.display_name ?? id;

  async function handleAdd() {
    setError(null);
    if (!area || Number(area) <= 0) {
      setError('Enter a positive area.');
      return;
    }
    if (!baseGlazingId) {
      setError('Pick a base glazing.');
      return;
    }
    setAdding(true);
    try {
      const updated = await api.addFace(project.id, {
        orientation,
        area_sqft: Number(area),
        base_glazing_id: baseGlazingId,
        count: Number(count) || 1,
      });
      onProjectUpdate(updated);
      setArea('');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAdding(false);
    }
  }

  return (
    <div>
      {project.faces.length > 0 ? (
        <div className="overflow-hidden rounded-md border border-ink/10">
          <table className="w-full text-sm">
            <thead className="bg-neutralbg text-left text-xs uppercase tracking-wide text-ink/60">
              <tr>
                <th className="px-3 py-2">Orientation</th>
                <th className="px-3 py-2">Area (sf)</th>
                <th className="px-3 py-2">Count</th>
                <th className="px-3 py-2">Base glazing</th>
              </tr>
            </thead>
            <tbody>
              {project.faces.map((f) => (
                <tr key={f.id} className="border-t border-ink/10">
                  <td className="px-3 py-2 font-medium text-ink">
                    {f.orientation}
                  </td>
                  <td className="px-3 py-2">{f.area_sqft.toLocaleString()}</td>
                  <td className="px-3 py-2">{f.count}</td>
                  <td className="px-3 py-2 text-ink/80">
                    {glazingName(f.base_glazing_id)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-ink/60">
          No glazing faces yet. Add at least one face to run an analysis.
        </p>
      )}

      <div className="mt-4 rounded-md border border-dashed border-ink/20 p-4">
        <div className="grid items-end gap-3 sm:grid-cols-5">
          <div>
            <Label>Orientation</Label>
            <Select
              value={orientation}
              onChange={(e) => setOrientation(e.target.value)}
            >
              {ORIENTATIONS.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label>Area (sf)</Label>
            <TextInput
              type="number"
              value={area}
              onChange={(e) => setArea(e.target.value)}
            />
          </div>
          <div>
            <Label>Count</Label>
            <TextInput
              type="number"
              value={count}
              onChange={(e) => setCount(e.target.value)}
            />
          </div>
          <div className="sm:col-span-2">
            <Label>Base glazing</Label>
            <Select
              value={baseGlazingId}
              onChange={(e) => setBaseGlazingId(e.target.value)}
            >
              {baseGlazings.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.display_name} (SHGC {g.shgc}, U {g.u_factor_btuhrft2F}, VT{' '}
                  {g.vt})
                </option>
              ))}
            </Select>
          </div>
        </div>
        {error && (
          <div className="mt-3">
            <ErrorBox message={error} />
          </div>
        )}
        <div className="mt-3">
          <Button variant="secondary" onClick={handleAdd} disabled={adding}>
            {adding ? 'Adding…' : '+ Add face'}
          </Button>
        </div>
      </div>
    </div>
  );
}
