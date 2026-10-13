import { useEffect, useMemo, useState } from 'react';
import { skillsService } from '../services/skillsService';
import { storage } from '../utils/storage';
import type { SkillsTeamRow } from '../types';
import { stateBadgeClass, stateLabel } from '../utils/skills';
import Icon from '../components/Icon';

export default function SkillsTeamPage() {
  const [team, setTeam] = useState<SkillsTeamRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [dept, setDept] = useState('');

  useEffect(() => {
    skillsService.team()
      .then(r => setTeam(r.team))
      .catch(() => setError('Failed to load the team directory.'))
      .finally(() => setLoading(false));
  }, []);

  const departments = useMemo(
    () => Array.from(new Set(team.map(t => t.department).filter(Boolean))).sort(),
    [team]
  );

  const filtered = useMemo(() => team.filter(t => {
    if (dept && t.department !== dept) return false;
    if (search) {
      const q = search.toLowerCase();
      if (!t.name.toLowerCase().includes(q) && !t.employee_id.toLowerCase().includes(q)) return false;
    }
    return true;
  }), [team, dept, search]);

  const submitted = team.filter(t => ['submitted', 'approved'].includes(t.compliance)).length;
  const [exporting, setExporting] = useState(false);

  async function exportXlsx() {
    setExporting(true); setError('');
    try {
      const token = storage.getAccessToken();
      const resp = await fetch(skillsService.exportUrl({ status: 'all' }), {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) { setError('Export failed.'); return; }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'JSAN_QF09_Skill_Matrix_all-cycles_all.xlsx';
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch { setError('Export failed.'); }
    finally { setExporting(false); }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Team Skills</h1>
          <p className="page-subtitle">Each person's status for the active review cycle</p>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span className="muted">{submitted}/{team.length} submitted</span>
          <button className="btn btn-secondary" onClick={exportXlsx} disabled={exporting}>
            {exporting ? 'Exporting…' : <><Icon name="file" size={15} /> Export Excel</>}
          </button>
        </div>
      </div>

      {error && <div className="error-message" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="filters-bar" style={{ marginBottom: 16 }}>
        <input className="search-input" placeholder="Search name or ID…" value={search} onChange={e => setSearch(e.target.value)} />
        <select className="filter-select" value={dept} onChange={e => setDept(e.target.value)}>
          <option value="">All departments</option>
          {departments.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
      </div>

      {loading ? (
        <div className="loading-state"><div className="spinner" /><p>Loading…</p></div>
      ) : (
        <div className="card">
          <table className="kt-table">
            <thead><tr><th>Employee ID</th><th>Name</th><th>Department</th><th>Designation</th><th>Active cycle</th></tr></thead>
            <tbody>
              {filtered.map(t => (
                <tr key={t.employee_id}>
                  <td><code style={{ fontSize: 12 }}>{t.employee_id}</code></td>
                  <td>{t.name}</td>
                  <td>{t.department || '—'}</td>
                  <td>{t.designation || '—'}</td>
                  <td><span className={`badge ${stateBadgeClass(t.compliance)}`}>{stateLabel(t.compliance)}</span></td>
                </tr>
              ))}
              {filtered.length === 0 && <tr><td colSpan={5} className="muted" style={{ textAlign: 'center', padding: 24 }}>No matches.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
