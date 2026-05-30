import { useRef, useState } from 'react';
import { api } from '../api';
import type { BaseGlazing, Project } from '../types';
import { Button, ErrorBox, Label, Select, TextInput } from './ui';

// 8-point compass (the resolution surveyors record at) + H for skylights.
const ORIENTATIONS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'H'];

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
  const [tiltDeg, setTiltDeg] = useState('');
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [importMsg, setImportMsg] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  const glazingName = (id: string) =>
    baseGlazings.find((g) => g.id === id)?.display_name ?? id;

  async function handleImport(file: File) {
    setError(null);
    setImportMsg(null);
    setImporting(true);
    try {
      const res = await api.importSurvey(project.id, file, 'replace');
      onProjectUpdate(res.project);
      setImportMsg(
        `Imported ${res.imported} face${res.imported === 1 ? '' : 's'} from ${file.name}.`,
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

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
        tilt_deg: tiltDeg ? Number(tiltDeg) : null,
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
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-xs text-ink/60">
          Add faces individually below, or import a 3M/IWFA survey workbook
          (.xlsx) to populate them all at once.
        </p>
        <div className="flex items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void handleImport(f);
            }}
          />
          <Button
            variant="secondary"
            disabled={importing}
            onClick={() => fileRef.current?.click()}
          >
            {importing ? 'Importing…' : 'Import survey (.xlsx)'}
          </Button>
        </div>
      </div>
      {importMsg && (
        <div className="mb-3 rounded-md bg-green-50 px-3 py-2 text-xs text-green-800">
          {importMsg}
        </div>
      )}

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
        <div className="grid items-end gap-3 sm:grid-cols-6">
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
          <div>
            <Label>Tilt° (optional)</Label>
            <TextInput
              type="number"
              step="1"
              value={tiltDeg}
              onChange={(e) => setTiltDeg(e.target.value)}
              placeholder="90 vert · 0 horiz"
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
