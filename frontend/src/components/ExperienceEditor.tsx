import type { ExperienceItem } from '../types';

const MAX = 20;
const blank = (): ExperienceItem => ({ company: '', role: '', years: '' });

interface Props {
  value: ExperienceItem[];
  onChange: (items: ExperienceItem[]) => void;
}

/**
 * Previous-experience editor: first a count of previous companies, then that
 * many {Company, Role, Years} rows. Changing the count grows/shrinks the rows.
 */
export default function ExperienceEditor({ value, onChange }: Props) {
  const items = value || [];

  const setCount = (nRaw: string) => {
    const n = Math.max(0, Math.min(MAX, Number(nRaw) || 0));
    if (n === items.length) return;
    if (n < items.length) {
      onChange(items.slice(0, n));
    } else {
      onChange([...items, ...Array.from({ length: n - items.length }, blank)]);
    }
  };

  const setField = (i: number, field: keyof ExperienceItem, val: string) => {
    onChange(items.map((it, idx) => (idx === i ? { ...it, [field]: val } : it)));
  };

  return (
    <div>
      <div className="form-group" style={{ maxWidth: 280 }}>
        <label className="form-label">Number of previous companies</label>
        <input
          type="number" min={0} max={MAX} className="form-input"
          value={items.length}
          onChange={e => setCount(e.target.value)}
          placeholder="0"
        />
      </div>

      {items.map((it, i) => (
        <div className="form-grid" key={i} style={{ marginTop: 4 }}>
          <div className="form-group">
            <label className="form-label">Company {i + 1}</label>
            <input className="form-input" value={it.company} onChange={e => setField(i, 'company', e.target.value)} placeholder="Company name" />
          </div>
          <div className="form-group">
            <label className="form-label">Role {i + 1}</label>
            <input className="form-input" value={it.role} onChange={e => setField(i, 'role', e.target.value)} placeholder="Designation / role" />
          </div>
          <div className="form-group">
            <label className="form-label">Years {i + 1}</label>
            <input className="form-input" value={it.years} onChange={e => setField(i, 'years', e.target.value)} placeholder="e.g. 2.5" inputMode="decimal" />
          </div>
        </div>
      ))}
    </div>
  );
}
